"""Жұмбақ дня по запросу: публикация, попытки, вечерний разбор и рейтинг."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from html import escape

from app.application.ports.channel import ChannelPost, ChannelPublisher
from app.application.ports.content import (
    ContentRepository,
    PostLogEntry,
    PostLogRepository,
    QuizAnswerRepository,
)
from app.application.ports.riddles import PublicationGate, RiddleAnswerRepository
from app.application.services.quiz_service import Answerer
from app.domain.catalog.daily import TZ
from app.domain.channel.content.answers.result import LEADERBOARD_SIZE, QuizStats, render_result
from app.domain.channel.content.daily_riddle import (
    MAX_ATTEMPTS,
    check_riddle_answer,
    daily_riddle_closes,
    daily_riddle_key,
    is_daily_riddle,
    render_daily_riddle,
)
from app.domain.channel.content.item import QuizOpen
from app.domain.channel.content.kinds import ContentKind
from app.domain.channel.content.plan import Source
from app.domain.subscription.weekly import week_start


@dataclass(frozen=True, slots=True)
class RiddleReply:
    text: str
    message_id: int | None = None


class DailyRiddleService:
    def __init__(
        self, items: ContentRepository, log: PostLogRepository,
        answers: RiddleAnswerRepository, stats: QuizAnswerRepository,
        publisher: ChannelPublisher, gate: PublicationGate, admin_ids: Collection[int],
    ) -> None:
        self._items = items
        self._log = log
        self._answers = answers
        self._stats = stats
        self._publisher = publisher
        self._gate = gate
        self._admin_ids = set(admin_ids)

    async def request(self, now: datetime) -> RiddleReply:
        key = daily_riddle_key(now)
        async with self._gate.hold(key) as acquired:
            if not acquired:
                return RiddleReply("Жұмбақ дайындалып жатыр. Сәлден кейін қайта басыңыз 🙂")
            existing = await self._log.by_slot_key(key)
            if existing is not None:
                item = await self._items.get(existing.item_id)
                question = (item.payload.question
                            if item and isinstance(item.payload, QuizOpen) else "")
                text = f"🧩 Бүгінгі жұмбақ:\n{question}\n\nТолық пост пен жауаптар — каналда."
                return RiddleReply(text, existing.channel_message_id)
            if now >= daily_riddle_closes(now):
                return RiddleReply("Бүгінгі ойын уақыты аяқталды. Ертең 21:00-ге дейін келіңіз 🙂")
            item = await self._items.next_for(
                Source(ContentKind.QUIZ_OPEN, topic="zhumbaq"), now.astimezone(TZ).date(),
            )
            if item is None or item.id is None or not isinstance(item.payload, QuizOpen):
                return RiddleReply("Жұмбақтар әзірге дайын емес. Кейінірек көріңіз 🙂")
            sent = await self._publisher.publish(ChannelPost(text=render_daily_riddle(item)))
            if sent is None:
                return RiddleReply("Жариялау мүмкін болмады. Қайта көріңіз.")
            await self._log.add(PostLogEntry(
                slot_key=key, item_id=item.id, kind=item.kind, channel_message_id=sent,
                posted_at=now, quiz_closes_at=daily_riddle_closes(now),
            ))
            await self._items.mark_posted(item.id, now)
            return RiddleReply("Бүгінгі жұмбақ каналда жарияланды 🧩", sent)

    async def answer(
        self, who: Answerer, text: str, now: datetime, *, thread_id: int | None = None,
        comments_only: bool = False,
    ) -> RiddleReply | None:
        post = await self._log.get_by_group_message(thread_id) if thread_id is not None else None
        if post is None or not is_daily_riddle(post.slot_key):
            if comments_only:
                return None
            post = await self._log.by_slot_key(daily_riddle_key(now))
        if post is None or post.id is None:
            return RiddleReply("Бүгінгі жұмбақ әлі ашылған жоқ. /jumbak деп жазыңыз.")
        if post.quiz_closes_at is None or now >= post.quiz_closes_at:
            return RiddleReply("⏳ Жауап қабылдау аяқталды. Қорытынды үшін /answer деп жазыңыз.")
        item = await self._items.get(post.item_id)
        if item is None or not isinstance(item.payload, QuizOpen):
            return RiddleReply("Жұмбақ табылмады.")
        if not text.strip() or len(text) > 255:
            return RiddleReply("Бір қысқа жауап жазыңыз: /answer жауабыңыз")
        correct = check_riddle_answer(item.payload, text)
        if who.user_id in self._admin_ids:
            return RiddleReply("✅ Дұрыс! (Тексеру, ұпай есептелмейді.)" if correct else "❌ Қате.")
        attempt = await self._answers.attempt(
            post.id, who.user_id, who.first_name, text, correct, now,
        )
        if not attempt.recorded:
            return RiddleReply("Сіз дұрыс жауап беріп қойдыңыз ✅" if attempt.correct
                               else "Үш мүмкіндік те қолданылды. Қорытынды — 21:00-ден кейін.")
        if correct:
            return RiddleReply(f"✅ Дұрыс! +{attempt.points} ұпай. Жарайсыз!")
        remaining = MAX_ATTEMPTS - attempt.attempts
        return RiddleReply(f"❌ Қате. Қалған мүмкіндік: {remaining}." if remaining
                           else "❌ Қате. Мүмкіндік қалмады. Жауабы — 21:00-ден кейін.")

    async def result(self, now: datetime) -> RiddleReply:
        post = await self._log.by_slot_key(daily_riddle_key(now))
        if post is None or post.id is None:
            return RiddleReply("Бүгінгі жұмбақ әлі ашылған жоқ. /jumbak деп жазыңыз.")
        if post.quiz_closes_at is None or now < post.quiz_closes_at:
            return RiddleReply("⏳ Жауабы мен қорытындысы 21:00-ден кейін (Алматы уақыты).")
        key = f"{post.slot_key}:result"
        async with self._gate.hold(key) as acquired:
            if not acquired:
                return RiddleReply("Қорытынды дайындалып жатыр. Сәлден кейін қайталаңыз.")
            existing = await self._log.by_slot_key(key)
            if existing is not None:
                return RiddleReply("Бүгінгі қорытынды жарияланған 🏆", existing.channel_message_id)
            item = await self._items.get(post.item_id)
            if item is None:
                return RiddleReply("Жұмбақ табылмады.")
            row = await self._stats.stats(post.id, LEADERBOARD_SIZE)
            sent = await self._publisher.publish(ChannelPost(
                text=render_result(item, QuizStats(row.total, row.correct, row.first_correct)),
            ))
            if sent is None:
                return RiddleReply("Қорытындыны жариялау мүмкін болмады. Қайта көріңіз.")
            await self._log.add(PostLogEntry(
                slot_key=key, item_id=post.item_id, kind=post.kind,
                channel_message_id=sent, posted_at=now,
            ))
            await self._log.mark_result_posted(post.id, now)
            return RiddleReply("Жауабы мен қорытындысы каналда жарияланды 🏆", sent)

    async def rating(self, user_id: int, now: datetime) -> str:
        start = datetime.combine(week_start(now), time(), tzinfo=TZ)
        rows = await self._answers.leaders(start, start + timedelta(days=7))
        lines = ["🏆 <b>Жұмбақ · апталық рейтинг</b>", ""]
        if not rows:
            return "\n".join((*lines, "Әзірге ұпай жинаған ешкім жоқ. /jumbak деп бастаңыз!"))
        rank, previous = 0, None
        own = "Сізде әзірге ұпай жоқ."
        for index, row in enumerate(rows, start=1):
            if row.points != previous:
                rank, previous = index, row.points
            label = escape(" ".join(row.name.split())[:40])
            if index <= LEADERBOARD_SIZE:
                lines.append(f"{rank}. {label} — {row.points} ұпай · {row.solved} жұмбақ")
            if row.user_id == user_id:
                own = f"Сіздің орныңыз: {rank} · {row.points} ұпай."
        return "\n".join((*lines, "", own))
