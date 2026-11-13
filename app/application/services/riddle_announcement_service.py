"""Ручной анонс с общей кнопкой: публикуется один раз и закрепляется."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from app.application.ports.channel import ChannelPost, ChannelPublisher
from app.application.ports.content import ContentRepository, PostLogEntry, PostLogRepository
from app.application.ports.riddles import PublicationGate, RiddleAnswerRepository
from app.domain.channel.content.daily_riddle import DAILY_RIDDLE_CALLBACK
from app.domain.channel.content.kinds import ContentKind
from app.domain.channel.content.render.base import CallbackButton, ContentRenderer

_KEY = "announcement:daily-riddle"


@dataclass(frozen=True, slots=True)
class AnnouncementOutcome:
    text: str
    message_id: int | None = None
    pinned: bool = False


class RiddleAnnouncementService:
    def __init__(
        self, items: ContentRepository, log: PostLogRepository, publisher: ChannelPublisher,
        gate: PublicationGate, answers: RiddleAnswerRepository,
        renderers: Mapping[ContentKind, ContentRenderer],
    ) -> None:
        self._items = items
        self._log = log
        self._publisher = publisher
        self._gate = gate
        self._answers = answers
        self._renderers = renderers

    async def publish_and_pin(self, now: datetime) -> AnnouncementOutcome:
        # Проверяем загруженный банк и новую схему ПЕРЕД публикацией обещания в канал.
        counts = await self._items.count_by_kind()
        if counts.get(ContentKind.QUIZ_OPEN, 0) < 300:
            return AnnouncementOutcome("Банк загадок ещё не загружен: сначала выполните seed.")
        await self._answers.leaders(now, now)
        async with self._gate.hold(_KEY) as acquired:
            if not acquired:
                return AnnouncementOutcome("Анонс уже публикуется другим запросом.")
            existing = await self._log.by_slot_key(_KEY)
            if existing is not None:
                sent = existing.channel_message_id
            else:
                item = await self._items.by_slug("daily-riddle-launch")
                if item is None or item.id is None:
                    return AnnouncementOutcome("Текст анонса не загружен: сначала выполните seed.")
                post = self._renderers[item.kind].render(item)
                sent = await self._publisher.publish(ChannelPost(
                    text=post.head,
                    choices=(CallbackButton("🧩 Күннің жұмбағы", DAILY_RIDDLE_CALLBACK),),
                ))
                if sent is None:
                    return AnnouncementOutcome("Анонс не опубликован. Повторите запуск.")
                await self._log.add(PostLogEntry(
                    slot_key=_KEY, item_id=item.id, kind=item.kind,
                    channel_message_id=sent, posted_at=now,
                ))
                await self._items.mark_posted(item.id, now)
            if not await self._publisher.pin(sent):
                return AnnouncementOutcome(
                    "Анонс опубликован, но не закреплён. Повторите запуск.", sent,
                )
            return AnnouncementOutcome("Анонс опубликован и закреплён.", sent, pinned=True)
