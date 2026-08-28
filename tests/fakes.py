"""Фейки, общие для юнит-тестов сервисов (без БД).

Журнал событий: его порт появился сразу у трёх сервисов (auth/playback/subscription),
и копировать один и тот же заглушечный класс в каждый тест-файл смысла нет. Плюс
пара мелких фейков под `AnalyticsService` (каталог + история снимков).
"""

from __future__ import annotations

from datetime import date, datetime

from app.domain.analytics.events import EventKind
from app.domain.analytics.milestone import Milestone
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
    """Фейк `DailyReportRepository`: держит снимки в памяти, отдаёт по диапазону дат."""

    def __init__(self, seed: list[DailyReport] | None = None) -> None:
        self.saved: list[DailyReport] = list(seed or [])

    async def save(self, report: DailyReport) -> None:
        self.saved = [r for r in self.saved if r.day != report.day] + [report]

    async def list_range(self, start: date, end: date) -> list[DailyReport]:
        return sorted((r for r in self.saved if start <= r.day <= end), key=lambda r: r.day)


class FakeMilestones:
    """Фейк `MilestoneRepository`: помнит добавленное, отдаёт по окну/лимиту."""

    def __init__(self) -> None:
        self.items: list[Milestone] = []
        self._next_id = 1

    async def add(self, label: str, occurred_at: datetime, created_by: int) -> Milestone:
        milestone = Milestone(self._next_id, occurred_at, label, created_by)
        self._next_id += 1
        self.items.append(milestone)
        return milestone

    async def list_recent(self, limit: int) -> list[Milestone]:
        return sorted(self.items, key=lambda m: m.occurred_at, reverse=True)[:limit]

    async def list_between(self, since: datetime, until: datetime) -> list[Milestone]:
        return sorted(
            (m for m in self.items if since <= m.occurred_at < until),
            key=lambda m: m.occurred_at,
        )
