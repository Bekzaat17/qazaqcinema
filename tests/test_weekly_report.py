"""Юнит-тесты еженедельного дайджеста (чистая сборка + текст, без БД)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from app.domain.analytics.milestone import Milestone
from app.domain.analytics.report import DailyReport
from app.domain.analytics.weekly_report import (
    build_weekly_report,
    previous_week_range,
    render_weekly_report,
    week_range,
)


def _daily(day: date, **overrides: int) -> DailyReport:
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


def test_week_range_covers_last_7_days_inclusive() -> None:
    start, end = week_range(date(2026, 8, 23))

    assert (start, end) == (date(2026, 8, 17), date(2026, 8, 23))


def test_previous_week_range_has_no_gap_and_no_overlap() -> None:
    cur_start, _ = week_range(date(2026, 8, 23))
    prev_start, prev_end = previous_week_range(date(2026, 8, 23))

    assert prev_end == cur_start - timedelta(days=1)  # без разрыва
    assert (prev_end - prev_start).days == 6  # тоже 7 суток


def test_build_weekly_report_sums_current_period_and_picks_latest_snapshot() -> None:
    current = [
        _daily(date(2026, 8, 17), catalog_size=100, users_total=300, opens_unique=6),
        _daily(date(2026, 8, 23), catalog_size=120, users_total=340, opens_unique=9),
    ]

    report = build_weekly_report(date(2026, 8, 23), current, [], [])

    assert report.catalog_size == 120  # последний снимок окна, не первый и не сумма
    assert report.users_total == 340
    assert report.current.opens_unique == 15  # сумма всех снимков окна
    assert report.previous is None  # истории за прошлую неделю не передали
    assert report.catalog_size_prev is None


def test_build_weekly_report_compares_latest_snapshots_of_each_period() -> None:
    current = [_daily(date(2026, 8, 23), catalog_size=120, subs_active=62)]
    previous = [_daily(date(2026, 8, 16), catalog_size=90, subs_active=57)]

    report = build_weekly_report(date(2026, 8, 23), current, previous, [])

    assert report.catalog_size_prev == 90
    assert report.subs_active_prev == 57
    assert report.previous is not None


def test_render_weekly_report_contains_period_and_key_numbers() -> None:
    current = [_daily(date(2026, 8, 23), catalog_size=120, users_total=340, subscribes=6)]
    previous = [_daily(date(2026, 8, 16), catalog_size=100, subscribes=4)]
    report = build_weekly_report(date(2026, 8, 23), current, previous, [])

    text = render_weekly_report(report)

    assert "17.08 – 23.08.2026" in text
    assert "120" in text  # каталог
    assert "340" in text  # всего юзеров
    assert "+20" in text  # рост каталога (120-100)
    assert "6" in text and "4" in text  # подписки: сейчас и на прошлой неделе


def test_render_weekly_report_notes_missing_history_without_previous() -> None:
    current = [_daily(date(2026, 8, 23))]
    report = build_weekly_report(date(2026, 8, 23), current, [], [])

    text = render_weekly_report(report)

    assert "деректер жеткіліксіз" in text


def test_render_weekly_report_lists_milestones_inside_the_period() -> None:
    current = [_daily(date(2026, 8, 23))]
    milestones = [Milestone(1, datetime(2026, 8, 20, 12, 0), "Күн фильмі іске қосылды", 1)]
    report = build_weekly_report(date(2026, 8, 23), current, [], milestones)

    text = render_weekly_report(report)

    assert "Күн фильмі іске қосылды" in text


def test_render_weekly_report_omits_milestones_section_when_empty() -> None:
    current = [_daily(date(2026, 8, 23))]
    report = build_weekly_report(date(2026, 8, 23), current, [], [])

    text = render_weekly_report(report)

    assert "вехалар" not in text


def test_render_weekly_report_escapes_milestone_label() -> None:
    """Метка — свободный текст админа: сырые `<`/`>` сломали бы HTML-разбор в Telegram."""
    current = [_daily(date(2026, 8, 23))]
    milestones = [Milestone(1, datetime(2026, 8, 20, 12, 0), "<script>тест</script>", 1)]
    report = build_weekly_report(date(2026, 8, 23), current, [], milestones)

    text = render_weekly_report(report)

    assert "<script>" not in text
    assert "&lt;script&gt;" in text
