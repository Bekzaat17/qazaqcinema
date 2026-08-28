"""Фейки, общие для юнит-тестов сервисов (без БД).

Журнал событий: его порт появился сразу у трёх сервисов (auth/playback/subscription),
и копировать один и тот же заглушечный класс в каждый тест-файл смысла нет. Плюс
пара мелких фейков под `AnalyticsService` (каталог + история снимков).
"""

from __future__ import annotations

from datetime import datetime

from app.domain.analytics.events import EventKind
from app.domain.analytics.report import DailyReport


class FakeEvents:
    """Фейк `UserEventRepository`: копит записанное, считает по накопленному."""

    def __init__(self) -> None:
        self.added: list[tuple[int, EventKind, str | None]] = []

    async def add(self, user_id: int, kind: EventKind, meta: str | None = None) -> None:
        self.added.append((user_id, kind, meta))

    async def count(self, kind: EventKind, since: datetime, until: datetime) -> int:
        return sum(1 for _, k, _m in self.added if k is kind)

    async def count_unique_users(
        self, kind: EventKind, since: datetime, until: datetime
    ) -> int:
        return len({user_id for user_id, k, _m in self.added if k is kind})

    def kinds_for(self, user_id: int) -> list[EventKind]:
        return [k for uid, k, _m in self.added if uid == user_id]


class FakeMovies:
    """Фейк `MovieRepository`, урезанный до того, что нужно `AnalyticsService` — размер каталога."""

    def __init__(self, catalog_size: int = 0) -> None:
        self.catalog_size = catalog_size

    async def count_all(self) -> int:
        return self.catalog_size


class FakeReports:
    """Фейк `DailyReportRepository`: помнит последний сохранённый снимок."""

    def __init__(self) -> None:
        self.saved: list[DailyReport] = []

    async def save(self, report: DailyReport) -> None:
        self.saved.append(report)
