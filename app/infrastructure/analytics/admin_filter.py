"""Декоратор журнала событий: действия админов в статистику не попадают.

Админ ходит по кинотеатру каждый день — проверяет новинки, тестирует выдачу видео,
открывает Mini App после каждой правки. В отчёте это выглядело бы как живая аудитория
и врало бы тем сильнее, чем меньше настоящих пользователей.

Отсекаем на ЗАПИСИ (а не при подсчёте): так админский шум не копится в таблице вообще,
и любой будущий запрос к истории — воронка, когорты, рефералка — автоматически чист,
без риска забыть фильтр. Декоратор поверх порта, а не флаг внутри Pg-адаптера: сам
`UserEventRepository` не должен знать, что где-то существуют админы (SRP + OCP).
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime

from app.application.ports.repositories import UserEventRepository
from app.domain.analytics.events import EventKind


class AdminBlindEventRepository:
    """`UserEventRepository`, который молча игнорирует события админов."""

    def __init__(self, inner: UserEventRepository, admin_ids: Collection[int]) -> None:
        self._inner = inner
        self._admins = frozenset(admin_ids)

    async def add(self, user_id: int, kind: EventKind, meta: str | None = None) -> None:
        if user_id in self._admins:
            return
        await self._inner.add(user_id, kind, meta)

    async def count(self, kind: EventKind, since: datetime, until: datetime) -> int:
        return await self._inner.count(kind, since, until)

    async def count_unique_users(
        self, kind: EventKind, since: datetime, until: datetime
    ) -> int:
        return await self._inner.count_unique_users(kind, since, until)
