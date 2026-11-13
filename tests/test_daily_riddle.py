"""Жұмбақ дня: состояние сохраняется между запросами, в канал не идут дубли."""

from __future__ import annotations

import asyncio
import unittest
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml
from app.application.ports.channel import ChannelPost
from app.application.ports.content import PostLogEntry, QuizStatsRow
from app.application.ports.riddles import RiddleAttempt, RiddleRank
from app.application.services.daily_riddle_service import DailyRiddleService
from app.application.services.quiz_service import Answerer, QuizService
from app.application.services.riddle_announcement_service import RiddleAnnouncementService
from app.domain.channel.content.daily_riddle import (
    DAILY_RIDDLE_CALLBACK,
    check_riddle_answer,
    daily_riddle_closes,
    daily_riddle_key,
    render_daily_riddle,
)
from app.domain.channel.content.item import ContentItem, QuizOpen
from app.domain.channel.content.kinds import ContentKind
from app.domain.channel.content.plan import Source
from app.domain.channel.content.render.greeting import GreetingRenderer

_NOW = datetime(2026, 11, 13, 7, tzinfo=UTC)
_USER = Answerer(42, "Айгүл")


class _Items:
    def __init__(self) -> None:
        self.bank_size = 396
        self.items = [ContentItem(
            id=i, slug=f"riddle-{i}", kind=ContentKind.QUIZ_OPEN, topic="zhumbaq",
            title_kk="Жұмбақ", body_kk="", payload=QuizOpen(f"Сұрақ {i}", ("Кірпі", "ёж")),
        ) for i in range(1, 4)]
        self.used: list[int] = []

    async def count_by_kind(self) -> dict[ContentKind, int]:
        return {ContentKind.QUIZ_OPEN: self.bank_size}

    async def by_slug(self, slug: str) -> ContentItem | None:
        if slug != "daily-riddle-launch":
            return None
        return ContentItem(
            id=10, slug=slug, kind=ContentKind.GREETING, topic="zhumbaq",
            title_kk="Сіздерді естідік! 💛", body_kk="Көпшіліктің сұрауымен!",
        )

    async def next_for(self, source: Source, today: object) -> ContentItem | None:
        return next((item for item in self.items if item.id not in self.used), None)

    async def mark_posted(self, item_id: int, at: datetime) -> None:
        self.used.append(item_id)

    async def get(self, item_id: int) -> ContentItem | None:
        return next((item for item in self.items if item.id == item_id), None)


class _Log:
    def __init__(self) -> None:
        self.entries: list[PostLogEntry] = []

    async def by_slot_key(self, slot_key: str) -> PostLogEntry | None:
        return next((entry for entry in self.entries if entry.slot_key == slot_key), None)

    async def add(self, entry: PostLogEntry) -> PostLogEntry | None:
        if await self.by_slot_key(entry.slot_key) is not None:
            return None
        entry = replace(entry, id=len(self.entries) + 1)
        self.entries.append(entry)
        return entry

    async def get_by_group_message(self, group_message_id: int) -> PostLogEntry | None:
        return next((e for e in self.entries if e.group_message_id == group_message_id), None)

    async def mark_result_posted(self, post_id: int, at: datetime) -> None:
        self.entries = [replace(e, result_posted_at=at) if e.id == post_id else e
                        for e in self.entries]

    async def list_due_results(self, now: datetime) -> list[PostLogEntry]:
        return [e for e in self.entries if e.quiz_closes_at and e.quiz_closes_at <= now]


class _Answers:
    def __init__(self) -> None:
        self.rows: dict[tuple[int, int], RiddleAttempt] = {}
        self.ranks: list[RiddleRank] = []
        self.period: tuple[datetime, datetime] | None = None

    async def attempt(
        self, post_id: int, user_id: int, name: str, text: str, correct: bool, at: datetime,
    ) -> RiddleAttempt:
        key = post_id, user_id
        current = self.rows.get(key)
        if current and (current.correct or current.attempts >= 3):
            return replace(current, recorded=False)
        attempt = RiddleAttempt(1 if current is None else current.attempts + 1, correct, True)
        self.rows[key] = attempt
        return attempt

    async def stats(self, post_id: int, first_n: int) -> QuizStatsRow:
        attempts = [v for (pid, _uid), v in self.rows.items() if pid == post_id]
        return QuizStatsRow(len(attempts), sum(a.correct for a in attempts), ())

    async def leaders(self, since: datetime, until: datetime) -> list[RiddleRank]:
        self.period = since, until
        return self.ranks


class _Publisher:
    def __init__(self) -> None:
        self.posts: list[ChannelPost] = []
        self.fail = False
        self.pin_fail = False
        self.pinned: list[int] = []

    async def pin(self, message_id: int) -> bool:
        if self.pin_fail:
            return False
        self.pinned.append(message_id)
        return True

    async def publish(self, post: ChannelPost) -> int | None:
        await asyncio.sleep(0)
        if self.fail:
            return None
        self.posts.append(post)
        return 100 + len(self.posts)


class _Gate:
    def __init__(self) -> None:
        self.active: set[str] = set()

    @asynccontextmanager
    async def hold(self, key: str) -> AsyncIterator[bool]:
        acquired = key not in self.active
        if acquired:
            self.active.add(key)
        try:
            yield acquired
        finally:
            if acquired:
                self.active.remove(key)


class DailyRiddleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.items, self.log, self.answers = _Items(), _Log(), _Answers()
        self.publisher, self.gate = _Publisher(), _Gate()
        self.service = self.new_service()

    def new_service(self) -> DailyRiddleService:
        return DailyRiddleService(
            self.items, self.log, self.answers, self.answers, self.publisher, self.gate, [1],
        )  # type: ignore[arg-type]

    async def test_old_buttons_and_restarts_keep_one_post_per_local_day(self) -> None:
        first = await self.service.request(_NOW)
        # Новый экземпляр сервиса не помнит запрос: источник правды — журнал, а не RAM.
        again = await self.new_service().request(_NOW + timedelta(hours=1))
        self.assertEqual(first.message_id, again.message_id)
        self.assertIn("Сұрақ 1", again.text)
        self.assertEqual(len(self.publisher.posts), 1)
        tomorrow = await self.service.request(_NOW + timedelta(days=1))
        self.assertNotEqual(first.message_id, tomorrow.message_id)
        self.assertEqual(self.items.used, [1, 2])
        self.assertEqual(DAILY_RIDDLE_CALLBACK, "jumbak:today")

    async def test_simultaneous_clicks_publish_once(self) -> None:
        await asyncio.gather(*(self.service.request(_NOW) for _ in range(20)))
        self.assertEqual(len(self.publisher.posts), 1)
        self.assertEqual(len(self.log.entries), 1)

    async def test_failed_delivery_can_be_retried_without_consuming_riddle(self) -> None:
        self.publisher.fail = True
        self.assertIsNone((await self.service.request(_NOW)).message_id)
        self.assertEqual(self.items.used, [])
        self.publisher.fail = False
        self.assertIsNotNone((await self.service.request(_NOW)).message_id)

    async def test_wrong_answer_does_not_reveal_answer_and_success_awards_two_points(self) -> None:
        await self.service.request(_NOW)
        wrong = await self.service.answer(_USER, "қоян", _NOW)
        assert wrong is not None
        self.assertNotIn("Кірпі", wrong.text)
        correct = await self.service.answer(_USER, "кирпи", _NOW)
        assert correct is not None
        self.assertIn("+2 ұпай", correct.text)
        await self.service.answer(_USER, "қоян", _NOW)
        self.assertEqual(self.answers.rows[(1, 42)].attempts, 2)
        self.assertTrue(self.answers.rows[(1, 42)].correct)

    async def test_attempt_limit_is_per_user_and_cannot_be_reset_by_request(self) -> None:
        await self.service.request(_NOW)
        for _ in range(3):
            await self.service.answer(_USER, "қоян", _NOW)
        await self.service.request(_NOW)
        late = await self.service.answer(_USER, "кірпі", _NOW)
        assert late is not None
        self.assertIn("Үш мүмкіндік", late.text)
        self.assertFalse(self.answers.rows[(1, 42)].correct)
        other = await self.service.answer(Answerer(43, "Дана"), "кірпі", _NOW)
        assert other is not None
        self.assertIn("+3 ұпай", other.text)

    async def test_exact_closing_time_rejects_answers_and_does_not_publish(self) -> None:
        await self.service.request(_NOW)
        await self.service.answer(_USER, "кірпі", daily_riddle_closes(_NOW))
        self.assertEqual(self.answers.rows, {})
        self.assertEqual(len(self.publisher.posts), 1)

    async def test_empty_day_after_closing_does_not_create_unplayable_riddle(self) -> None:
        self.assertIsNone((await self.service.request(daily_riddle_closes(_NOW))).message_id)
        self.assertEqual(self.publisher.posts, [])

    async def test_requested_result_is_published_once_as_a_separate_post(self) -> None:
        await self.service.request(_NOW)
        self.assertIsNone((await self.service.result(_NOW)).message_id)
        after = daily_riddle_closes(_NOW)
        first = await self.service.result(after)
        again = await self.new_service().result(after)
        self.assertEqual(first.message_id, again.message_id)
        self.assertEqual(len(self.publisher.posts), 2)
        self.assertIn("Кірпі", self.publisher.posts[-1].text)
        self.assertIsNone(self.publisher.posts[-1].reply_to_message_id)
        self.assertEqual((await self.service.request(after)).message_id, 101)

    async def test_automatic_results_job_cannot_publish_daily_riddle_result(self) -> None:
        await self.service.request(_NOW)
        quiz = QuizService(
            self.items, self.log, self.answers, self.publisher, [],
        )  # type: ignore[arg-type]
        self.assertEqual(await quiz.publish_due_results(daily_riddle_closes(_NOW)), 0)
        self.assertEqual(len(self.publisher.posts), 1)

    async def test_regular_comments_are_not_counted_and_old_daily_comments_are_closed(self) -> None:
        self.assertIsNone(await self.service.answer(
            _USER, "сәлем", _NOW, thread_id=999, comments_only=True,
        ))
        await self.service.request(_NOW)
        self.log.entries[0] = replace(self.log.entries[0], group_message_id=200)
        closed = await self.service.answer(
            _USER, "кірпі", _NOW + timedelta(days=1), thread_id=200, comments_only=True,
        )
        assert closed is not None
        self.assertIn("аяқталды", closed.text)
        self.assertEqual(self.answers.rows, {})

    async def test_administrators_can_check_answers_without_entering_rating(self) -> None:
        await self.service.request(_NOW)
        await self.service.answer(Answerer(1, "Admin"), "кірпі", _NOW)
        self.assertEqual(self.answers.rows, {})

    async def test_weekly_rating_uses_almaty_week_shared_ranks_and_escaped_names(self) -> None:
        self.answers.ranks = [RiddleRank(42, "<Айгүл>", 6, 2), RiddleRank(43, "Дана", 6, 3)]
        text = await self.service.rating(43, _NOW)
        self.assertIn("1. &lt;Айгүл&gt;", text)
        self.assertIn("1. Дана", text)
        self.assertIn("орныңыз: 1", text)
        assert self.answers.period is not None
        start, end = self.answers.period
        self.assertEqual((start.weekday(), start.hour), (0, 0))
        self.assertEqual(end - start, timedelta(days=7))


class RiddleContentTests(unittest.TestCase):
    def test_local_day_rollover_is_at_1900_utc(self) -> None:
        before = datetime(2026, 11, 13, 18, 59, tzinfo=UTC)
        after = before + timedelta(minutes=1)
        self.assertEqual(daily_riddle_key(before), "2026-11-13:jumbak")
        self.assertEqual(daily_riddle_key(after), "2026-11-14:jumbak")

    def test_single_answer_normalization_allows_typos_but_not_lists_of_guesses(self) -> None:
        quiz = QuizOpen("?", ("Қарындаш", "карандаш"))
        self.assertTrue(check_riddle_answer(quiz, "  КАРЫНДАШ! "))
        self.assertTrue(check_riddle_answer(quiz, "қарындас"))
        self.assertFalse(check_riddle_answer(quiz, "қалам қарындаш кітап өшіргіш"))
        self.assertFalse(check_riddle_answer(quiz, ""))

    def test_bank_has_300_to_400_distinct_valid_riddles_with_accepted_answers(self) -> None:
        root = Path(__file__).resolve().parents[1] / "content"
        bank = [entry for path in root.glob("zhumbaq*.yaml")
                for entry in yaml.safe_load(path.read_text(encoding="utf-8"))]
        self.assertGreaterEqual(len(bank), 300)
        self.assertLessEqual(len(bank), 400)
        self.assertEqual(len({entry["slug"] for entry in bank}), len(bank))
        questions = [" ".join(entry["payload"]["question"].casefold().split()) for entry in bank]
        self.assertEqual(len(set(questions)), len(bank))
        for entry in bank:
            with self.subTest(slug=entry["slug"]):
                quiz = QuizOpen(entry["payload"]["question"], tuple(entry["payload"]["accept"]))
                self.assertTrue(all(a.strip() for a in quiz.accept))
                self.assertTrue(all(check_riddle_answer(quiz, a) for a in quiz.accept))
                item = ContentItem(
                    slug=entry["slug"], kind=ContentKind.QUIZ_OPEN, topic="zhumbaq",
                    title_kk=entry["title"], body_kk="", payload=quiz,
                )
                text = render_daily_riddle(item)
                self.assertLessEqual(len(text), 4096)
                self.assertNotIn("<b>Жауабы:", text)


class AnnouncementTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.items, self.log, self.publisher = _Items(), _Log(), _Publisher()
        self.service = RiddleAnnouncementService(
            self.items, self.log, self.publisher, _Gate(), _Answers(),
            {ContentKind.GREETING: GreetingRenderer()},
        )  # type: ignore[arg-type]

    async def test_announcement_is_pinned_and_all_future_clicks_use_today(self) -> None:
        first = await self.service.publish_and_pin(_NOW)
        again = await self.service.publish_and_pin(_NOW + timedelta(days=1))
        self.assertEqual(first.message_id, again.message_id)
        self.assertEqual(len(self.publisher.posts), 1)
        self.assertEqual(self.publisher.posts[0].choices[0].data, DAILY_RIDDLE_CALLBACK)
        self.assertEqual(self.publisher.pinned, [101, 101])

    async def test_missing_seed_prevents_premature_announcement(self) -> None:
        self.items.bank_size = 44
        self.assertIsNone((await self.service.publish_and_pin(_NOW)).message_id)
        self.assertEqual(self.publisher.posts, [])

    async def test_pin_failure_can_be_retried_without_reposting(self) -> None:
        self.publisher.pin_fail = True
        first = await self.service.publish_and_pin(_NOW)
        self.assertIn("не закреплён", first.text)
        self.publisher.pin_fail = False
        again = await self.service.publish_and_pin(_NOW)
        self.assertEqual(first.message_id, again.message_id)
        self.assertEqual(len(self.publisher.posts), 1)
        self.assertEqual(self.publisher.pinned, [101])


if __name__ == "__main__":
    unittest.main()
