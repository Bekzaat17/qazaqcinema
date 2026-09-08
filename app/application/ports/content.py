"""Порты контента канала (DIP): пул элементов, журнал публикаций, ответы на квизы.

Три мелких порта, а не один (ISP): сидер трогает только пул, джоб публикации — пул и
журнал, хендлеры квиза — журнал и ответы.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from app.domain.channel.content.item import ContentItem
from app.domain.channel.content.kinds import ContentKind
from app.domain.channel.content.plan import Source


class ContentRepository(Protocol):
    async def next_for(self, source: Source, today: date) -> ContentItem | None:
        """Следующий элемент источника для публикации — правило ротации живёт ЗДЕСЬ (в SQL):

        1. активный, подходящий по `kind` (и `topic`, если задан);
        2. сначала закреплённый на `today` (`scheduled_for = today`) — редакторский пин;
        3. затем никогда не постившиеся (`last_posted_at IS NULL`), потом самые давние — LRU;
        4. `source.repeat = False` → уже постившиеся не берём вовсе: пул исчерпан → None,
           и слот переходит к следующему источнику (см. `plan.Slot.sources`).
        Тай-брейк — `id`: порядок устойчив между прогонами.
        """
        ...

    async def mark_posted(self, item_id: int, at: datetime) -> None:
        """`last_posted_at = at`, `post_count += 1` — состояние ротации."""
        ...

    async def get(self, item_id: int) -> ContentItem | None: ...

    async def by_slug(self, slug: str) -> ContentItem | None:
        """Элемент по натуральному ключу — им поздравление находит свой текст.

        Ротация здесь ни при чём: какой пост нужен 21 наурыз, решает календарь
        (`domain/channel/holidays.py`), а не LRU-очередь пула."""
        ...

    async def upsert_many(self, items: list[ContentItem]) -> int:
        """Сидер: вставить/обновить по `slug` (натуральный ключ YAML). Состояние ротации
        (`last_posted_at`, `post_count`) НЕ трогает — правка текста не сбрасывает историю.
        Возвращает число обработанных."""
        ...

    async def count_by_kind(self) -> dict[ContentKind, int]:
        """Размер пула по формам — для сидера (что залито) и отчёта админам."""
        ...


@dataclass(frozen=True, slots=True)
class PostLogEntry:
    slot_key: str
    item_id: int
    kind: ContentKind
    channel_message_id: int
    posted_at: datetime
    quiz_closes_at: datetime | None = None
    group_message_id: int | None = None
    result_posted_at: datetime | None = None
    id: int | None = None


class PostLogRepository(Protocol):
    async def add(self, entry: PostLogEntry) -> PostLogEntry | None:
        """Записать публикацию. `slot_key` уже есть → None (дубль слота), без исключения."""
        ...

    async def exists(self, slot_key: str) -> bool: ...

    async def get_by_channel_message(self, channel_message_id: int) -> PostLogEntry | None: ...

    async def get_by_group_message(self, group_message_id: int) -> PostLogEntry | None:
        """Пост по id его авто-форварда в группе обсуждений (= `message_thread_id` комментариев)."""
        ...

    async def bind_group_message(self, channel_message_id: int, group_message_id: int) -> bool:
        """Связать пост канала с его форвардом в группе. False — такого поста в журнале нет."""
        ...

    async def list_due_results(self, now: datetime) -> list[PostLogEntry]:
        """Квизы, у которых время ответов вышло, а разбор ещё не опубликован."""
        ...

    async def mark_result_posted(self, post_id: int, at: datetime) -> None: ...


@dataclass(frozen=True, slots=True)
class QuizStatsRow:
    total: int
    correct: int
    first_correct: tuple[str, ...]


class QuizAnswerRepository(Protocol):
    async def add_first(
        self,
        post_id: int,
        user_id: int,
        first_name: str,
        text: str,
        is_correct: bool,
        at: datetime,
    ) -> bool:
        """Записать ответ, если человек ещё не отвечал на этот пост. False — уже отвечал
        (UNIQUE post+user в БД): засчитывается первый ответ, перебор вариантов не работает."""
        ...

    async def stats(self, post_id: int, first_n: int) -> QuizStatsRow:
        """Всего ответивших, верных, имена первых `first_n` правильных по времени."""
        ...
