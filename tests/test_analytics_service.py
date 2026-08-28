"""Юнит-тесты сбора отчёта и отсечки админов (без БД).

Проверяем две вещи: сервис действительно спрашивает у репозиториев то, что показывает
в отчёте, и админы не считаются — ни как события (декоратор `AdminBlindEventRepository`),
ни как люди (`exclude` в счётчиках юзеров).
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.application.services.analytics_service import AnalyticsService
from app.domain.analytics.events import EventKind
from app.domain.analytics.report import DailyReport
from app.infrastructure.analytics.admin_filter import AdminBlindEventRepository

from tests.fakes import FakeEvents, FakeMilestones, FakeMovies, FakeReports

ALMATY = ZoneInfo("Asia/Almaty")
_NOW = datetime(2026, 8, 13, 17, 0, tzinfo=UTC)  # 22:00 по Алматы
ADMIN = 1
USER = 2


def _snapshot(day: date, **overrides: int) -> DailyReport:
    base: dict[str, int] = {
        "users_total": 0,
        "users_new": 0,
        "subs_active": 0,
        "catalog_size": 0,
        "opens_total": 0,
        "opens_unique": 0,
        "starts": 0,
        "plays": 0,
        "free_plays": 0,
        "daily_plays": 0,
        "paywalls": 0,
        "subscribes": 0,
        "expires": 0,
    }
    base.update(overrides)
    return DailyReport(day=day, **base)  # type: ignore[arg-type]


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
        _CountingUsers(), events, FakeMovies(catalog_size=42), FakeReports(), FakeMilestones()
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
        users, FakeEvents(), FakeMovies(), FakeReports(), FakeMilestones(), [ADMIN]
    ).daily_report(_NOW, ALMATY)

    assert users.excluded == [[ADMIN], [ADMIN], [ADMIN]]


async def test_daily_report_is_persisted_to_history() -> None:
    reports = FakeReports()

    report = await AnalyticsService(
        _CountingUsers(), FakeEvents(), FakeMovies(catalog_size=7), reports, FakeMilestones()
    ).daily_report(_NOW, ALMATY)

    # Снимок пишется тем же вызовом, которым собирается текст для админов — не
    # отдельным джобом, иначе история отставала бы от реально отправленных отчётов.
    assert reports.saved == [report]


async def test_weekly_report_aggregates_saved_snapshots_and_compares_to_previous_week() -> None:
    """22:10 воскресенья: неделя — 17.08..23.08 (сегодня включительно), прошлая — 10.08..16.08."""
    sunday = datetime(2026, 8, 23, 17, 10, tzinfo=UTC)  # 22:10 по Алматы
    reports = FakeReports(
        seed=[
            _snapshot(date(2026, 8, 16), catalog_size=90, opens_unique=5, subscribes=1),
            _snapshot(date(2026, 8, 17), catalog_size=100, opens_unique=6, subscribes=1),
            _snapshot(date(2026, 8, 23), catalog_size=120, opens_unique=9, subscribes=2),
        ]
    )
    milestones = FakeMilestones()
    await milestones.add(
        "Күн фильмі іске қосылды", sunday - timedelta(days=2), created_by=ADMIN
    )
    await milestones.add("Ескі веха", sunday - timedelta(days=20), created_by=ADMIN)  # вне окна

    report = await AnalyticsService(
        _CountingUsers(), FakeEvents(), FakeMovies(), reports, milestones
    ).weekly_report(sunday, ALMATY)

    assert (report.period_start, report.period_end) == (date(2026, 8, 17), date(2026, 8, 23))
    assert report.catalog_size == 120  # последний снимок текущего окна
    assert report.catalog_size_prev == 90  # последний снимок ПРЕДЫДУЩЕГО (16.08)
    assert report.current.opens_unique == 6 + 9  # сумма снимков внутри текущего окна
    assert report.previous is not None and report.previous.opens_unique == 5
    assert [m.label for m in report.milestones] == ["Күн фильмі іске қосылды"]  # старая вне окна


async def test_weekly_report_without_history_has_no_previous_period() -> None:
    sunday = datetime(2026, 8, 23, 17, 10, tzinfo=UTC)
    reports = FakeReports(seed=[_snapshot(date(2026, 8, 23), catalog_size=10)])

    report = await AnalyticsService(
        _CountingUsers(), FakeEvents(), FakeMovies(), reports, FakeMilestones()
    ).weekly_report(sunday, ALMATY)

    assert report.previous is None
    assert report.catalog_size_prev is None


async def test_admin_events_are_not_recorded() -> None:
    inner = FakeEvents()
    journal = AdminBlindEventRepository(inner, [ADMIN])

    await journal.add(ADMIN, EventKind.OPEN)
    await journal.add(ADMIN, EventKind.PLAY, "7")
    await journal.add(USER, EventKind.OPEN)

    assert inner.added == [(USER, EventKind.OPEN, None)]
    assert await journal.count_unique_users(EventKind.OPEN, _NOW, _NOW) == 1
