"""Юнит-тесты домена отчёта: границы суток и текст (без БД, без Telegram).

Главное здесь — часовой пояс. Данные лежат в UTC, отчёт уходит в 23:00 по Алматы
(UTC+5): без пересчёта «сегодня» съехало бы на 5 часов и в сводку попадал бы хвост
вчерашнего дня.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.domain.analytics.report import DailyReport, day_window, render_report

ALMATY = ZoneInfo("Asia/Almaty")


def test_day_window_starts_at_local_midnight_in_utc() -> None:
    # 13 августа, 23:00 в Алматы = 18:00 UTC того же дня.
    now = datetime(2026, 8, 13, 18, 0, tzinfo=UTC)

    since, until = day_window(now, ALMATY)

    # Местная полночь 13-го = 19:00 UTC 12-го.
    assert since == datetime(2026, 8, 12, 19, 0, tzinfo=UTC)
    assert until == now


def test_day_window_covers_events_of_the_local_day_only() -> None:
    now = datetime(2026, 8, 13, 18, 0, tzinfo=UTC)
    since, _ = day_window(now, ALMATY)

    # Событие в 00:30 по Алматы (= 19:30 UTC вчера) — уже «сегодняшнее».
    just_after_midnight = datetime(2026, 8, 12, 19, 30, tzinfo=UTC)
    # А в 23:30 по Алматы предыдущего дня (= 18:30 UTC) — ещё вчерашнее.
    late_yesterday = datetime(2026, 8, 12, 18, 30, tzinfo=UTC)

    assert just_after_midnight >= since
    assert late_yesterday < since


def test_render_report_contains_all_numbers() -> None:
    report = DailyReport(
        day=date(2026, 8, 13),
        users_total=128,
        users_new=5,
        subs_active=34,
        opens_total=41,
        opens_unique=27,
        plays=63,
        free_plays=12,
        paywalls=19,
        subscribes=3,
        expires=1,
    )

    text = render_report(report)

    assert "13.08.2026" in text
    assert "128" in text and "+5" in text
    assert "34" in text
    assert "27 адам (41 рет)" in text
    assert "63" in text
    # Воронка: подарочные просмотры и упоры в пэйволл — обе цифры должны быть на виду,
    # иначе события пишутся в БД, но никто их не читает.
    assert "12" in text and "19" in text
