"""Юнит-тесты сбора отчёта и отсечки админов (без БД).

Проверяем две вещи: сервис действительно спрашивает у репозиториев то, что показывает
в отчёте, и админы не считаются — ни как события (декоратор `AdminBlindEventRepository`),
ни как люди (`exclude` в счётчиках юзеров).
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.application.services.analytics_service import AnalyticsService
from app.domain.analytics.events import EventKind
from app.infrastructure.analytics.admin_filter import AdminBlindEventRepository

from tests.fakes import FakeEvents, FakeMovies, FakeReports

ALMATY = ZoneInfo("Asia/Almaty")
_NOW = datetime(2026, 8, 13, 17, 0, tzinfo=UTC)  # 22:00 по Алматы
ADMIN = 1
USER = 2


class _CountingUsers:
    """Фейк UserRepository: помнит, с каким `exclude` его спрашивали."""

    def __init__(self) -> None:
        self.excluded: list[Collection[int]] = []

    async def count_all(self, exclude: Collection[int] = ()) -> int:
        self.excluded.append(exclude)
        return 10

    async def count_created_since(
        self, since: datetime, exclude: Collection[int] = ()
    ) -> int:
        self.excluded.append(exclude)
        return 2

    async def count_active(self, now: datetime, exclude: Collection[int] = ()) -> int:
        self.excluded.append(exclude)
        return 4


async def test_daily_report_collects_numbers() -> None:
    events = FakeEvents()
    await events.add(USER, EventKind.OPEN)
    await events.add(USER, EventKind.OPEN)  # тот же человек — одно уникальное открытие
    await events.add(3, EventKind.OPEN)
    await events.add(USER, EventKind.PLAY, "7")
    await events.add(USER, EventKind.DAILY_PLAY, "9")
    await events.add(USER, EventKind.START)

    report = await AnalyticsService(
        _CountingUsers(), events, FakeMovies(catalog_size=42), FakeReports()
    ).daily_report(_NOW, ALMATY)

    assert report.day.isoformat() == "2026-08-13"  # местная дата, не UTC
    assert (report.users_total, report.users_new, report.subs_active) == (10, 2, 4)
    assert report.catalog_size == 42
    assert (report.opens_total, report.opens_unique) == (3, 2)
    assert report.starts == 1
    assert report.plays == 1
    assert report.daily_plays == 1


async def test_admin_ids_are_excluded_from_user_counts() -> None:
    users = _CountingUsers()

    await AnalyticsService(
        users, FakeEvents(), FakeMovies(), FakeReports(), [ADMIN]
    ).daily_report(_NOW, ALMATY)

    assert users.excluded == [[ADMIN], [ADMIN], [ADMIN]]


async def test_daily_report_is_persisted_to_history() -> None:
    reports = FakeReports()

    report = await AnalyticsService(
        _CountingUsers(), FakeEvents(), FakeMovies(catalog_size=7), reports
    ).daily_report(_NOW, ALMATY)

    # Снимок пишется тем же вызовом, которым собирается текст для админов — не
    # отдельным джобом, иначе история отставала бы от реально отправленных отчётов.
    assert reports.saved == [report]


async def test_admin_events_are_not_recorded() -> None:
    inner = FakeEvents()
    journal = AdminBlindEventRepository(inner, [ADMIN])

    await journal.add(ADMIN, EventKind.OPEN)
    await journal.add(ADMIN, EventKind.PLAY, "7")
    await journal.add(USER, EventKind.OPEN)

    assert inner.added == [(USER, EventKind.OPEN, None)]
    assert await journal.count_unique_users(EventKind.OPEN, _NOW, _NOW) == 1
