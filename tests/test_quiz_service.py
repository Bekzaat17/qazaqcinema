"""QuizService: приём ответов кнопкой и комментарием, разбор. Фейки портов, без БД."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from app.application.ports.channel import ChannelPost
from app.application.ports.content import PostLogEntry, QuizStatsRow
from app.application.services.quiz_service import Answerer, QuizService, Verdict
from app.domain.channel.content.item import ContentItem, QuizChoice, QuizOpen
from app.domain.channel.content.kinds import ContentKind

NOW = datetime(2026, 9, 14, 8, 0, tzinfo=UTC)          # 13:00 Алматы
CLOSES = datetime(2026, 9, 14, 16, 0, tzinfo=UTC)      # 21:00 Алматы
ADMIN = 1
USER = Answerer(100, "Айгүл")

CHOICE = ContentItem(
    id=1, slug="maqal-01", kind=ContentKind.QUIZ_CHOICE, topic="maqal", title_kk="", body_kk="",
    payload=QuizChoice("Еңбек етсең ерінбей…", ("тояды қарның тіленбей", "жоқ"), 0),
)
OPEN = ContentItem(
    id=2, slug="zhumbaq-01", kind=ContentKind.QUIZ_OPEN, topic="zhumbaq", title_kk="", body_kk="",
    payload=QuizOpen("Жұмбақ", ("құлын",)),
)


class FakeItems:
    def __init__(self, *items: ContentItem) -> None:
        self._items = {i.id: i for i in items}

    async def get(self, item_id: int) -> ContentItem | None:
        return self._items.get(item_id)


class FakeLog:
    def __init__(self, *entries: PostLogEntry) -> None:
        self.entries = list(entries)
        self.result_posted: list[int] = []

    async def get_by_channel_message(self, channel_message_id: int) -> PostLogEntry | None:
        return next((e for e in self.entries if e.channel_message_id == channel_message_id), None)

    async def get_by_group_message(self, group_message_id: int) -> PostLogEntry | None:
        return next((e for e in self.entries if e.group_message_id == group_message_id), None)

    async def bind_group_message(self, channel_message_id: int, group_message_id: int) -> bool:
        for i, e in enumerate(self.entries):
            if e.channel_message_id == channel_message_id:
                self.entries[i] = replace(e, group_message_id=group_message_id)
                return True
        return False

    async def list_due_results(self, now: datetime) -> list[PostLogEntry]:
        return [
            e for e in self.entries
            if e.quiz_closes_at and e.quiz_closes_at <= now and e.result_posted_at is None
        ]

    async def mark_result_posted(self, post_id: int, at: datetime) -> None:
        self.result_posted.append(post_id)
        self.entries = [
            replace(e, result_posted_at=at) if e.id == post_id else e for e in self.entries
        ]


class FakeAnswers:
    def __init__(self) -> None:
        self.rows: list[tuple[int, int, str, str, bool, datetime]] = []

    async def add_first(
        self, post_id: int, user_id: int, first_name: str, text: str, is_correct: bool, at: datetime
    ) -> bool:
        if any(r[0] == post_id and r[1] == user_id for r in self.rows):
            return False
        self.rows.append((post_id, user_id, first_name, text, is_correct, at))
        return True

    async def stats(self, post_id: int, first_n: int) -> QuizStatsRow:
        rows = [r for r in self.rows if r[0] == post_id]
        correct = sorted((r for r in rows if r[4]), key=lambda r: r[5])
        return QuizStatsRow(len(rows), len(correct), tuple(r[2] for r in correct[:first_n]))


class FakePublisher:
    def __init__(self) -> None:
        self.posts: list[ChannelPost] = []
        self.removed: list[int] = []

    async def publish(self, post: ChannelPost) -> int | None:
        self.posts.append(post)
        return 500 + len(self.posts)

    async def remove_buttons(self, message_id: int) -> bool:
        self.removed.append(message_id)
        return True

    async def delete(self, message_id: int) -> bool:
        return True


def _entry(item: ContentItem, channel_id: int, group_id: int | None = None) -> PostLogEntry:
    return PostLogEntry(
        id=item.id, slot_key=f"2026-09-14:{item.slug}", item_id=item.id or 0, kind=item.kind,
        channel_message_id=channel_id, group_message_id=group_id, posted_at=NOW,
        quiz_closes_at=CLOSES,
    )


def _service(log: FakeLog, answers: FakeAnswers, publisher: FakePublisher) -> QuizService:
    return QuizService(FakeItems(CHOICE, OPEN), log, answers, publisher, [ADMIN])  # type: ignore[arg-type]


async def test_button_correct_then_second_press_is_ignored() -> None:
    log, answers = FakeLog(_entry(CHOICE, 10)), FakeAnswers()
    service = _service(log, answers, FakePublisher())

    first = await service.answer_choice(10, 1, 0, USER, NOW)
    assert first.verdict is Verdict.CORRECT
    second = await service.answer_choice(10, 1, 1, USER, NOW)
    assert second.verdict is Verdict.ALREADY_ANSWERED
    assert len(answers.rows) == 1 and answers.rows[0][4] is True


async def test_wrong_button_reports_the_answer() -> None:
    service = _service(FakeLog(_entry(CHOICE, 10)), FakeAnswers(), FakePublisher())
    outcome = await service.answer_choice(10, 1, 1, USER, NOW)
    assert outcome.verdict is Verdict.WRONG
    assert outcome.correct_answer == "тояды қарның тіленбей"


async def test_button_from_unknown_post_or_wrong_item_is_not_a_quiz() -> None:
    service = _service(FakeLog(_entry(CHOICE, 10)), FakeAnswers(), FakePublisher())
    assert (await service.answer_choice(99, 1, 0, USER, NOW)).verdict is Verdict.NOT_A_QUIZ
    assert (await service.answer_choice(10, 2, 0, USER, NOW)).verdict is Verdict.NOT_A_QUIZ


async def test_answers_after_closing_time_are_not_recorded() -> None:
    answers = FakeAnswers()
    service = _service(FakeLog(_entry(CHOICE, 10)), answers, FakePublisher())
    late = await service.answer_choice(10, 1, 0, USER, CLOSES + timedelta(minutes=1))
    assert late.verdict is Verdict.CLOSED and answers.rows == []


async def test_admin_answers_are_checked_but_not_counted() -> None:
    answers = FakeAnswers()
    service = _service(FakeLog(_entry(CHOICE, 10)), answers, FakePublisher())
    outcome = await service.answer_choice(10, 1, 0, Answerer(ADMIN, "Бекзат"), NOW)
    assert outcome.verdict is Verdict.CORRECT and answers.rows == []


async def test_comment_in_open_quiz_thread_is_checked_with_normalization() -> None:
    log, answers = FakeLog(_entry(OPEN, 20, group_id=300)), FakeAnswers()
    service = _service(log, answers, FakePublisher())

    outcome = await service.answer_comment(300, USER, "Менің ойымша, кулын", NOW)
    assert outcome.verdict is Verdict.CORRECT
    assert answers.rows[0][3] == "Менің ойымша, кулын"


async def test_comment_under_non_quiz_post_is_left_alone() -> None:
    log = FakeLog(_entry(CHOICE, 10, group_id=300))   # ветка под квизом с кнопками — не open
    service = _service(log, FakeAnswers(), FakePublisher())
    assert (await service.answer_comment(300, USER, "сәлем", NOW)).verdict is Verdict.NOT_A_QUIZ
    assert (await service.answer_comment(999, USER, "сәлем", NOW)).verdict is Verdict.NOT_A_QUIZ


async def test_forward_binding_enables_comments() -> None:
    log = FakeLog(_entry(OPEN, 20))
    service = _service(log, FakeAnswers(), FakePublisher())
    assert await service.bind_forward(20, 300) is True
    assert await service.bind_forward(21, 301) is False
    assert (await service.answer_comment(300, USER, "құлын", NOW)).verdict is Verdict.CORRECT


async def test_due_results_remove_buttons_and_reply_to_the_post() -> None:
    log, answers, publisher = FakeLog(_entry(CHOICE, 10)), FakeAnswers(), FakePublisher()
    service = _service(log, answers, publisher)
    for i, (name, idx) in enumerate([("Ерлан", 1), ("Айгүл", 0), ("Дана", 0)]):
        await service.answer_choice(10, 1, idx, Answerer(200 + i, name), NOW + timedelta(minutes=i))

    assert await service.publish_due_results(NOW) == 0      # ещё не 21:00
    assert await service.publish_due_results(CLOSES) == 1
    assert publisher.removed == [10]
    result = publisher.posts[0]
    assert result.reply_to_message_id == 10
    assert "3 адам жауап берді, 2 дұрыс тапты" in result.text
    assert "🥇 Айгүл · 🥈 Дана" in result.text
    assert log.result_posted == [1]
    assert await service.publish_due_results(CLOSES) == 0   # второй раз — уже отмечен
