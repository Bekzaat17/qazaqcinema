from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.subscription.expiry import compute_expiry
from app.domain.tariffs.tariff import Tariff

DAY = Tariff("1_day", "1 день", "1 күн", 349, timedelta(days=1))
MONTH = Tariff("1_month", "1 месяц", "1 ай", 1899, timedelta(days=30))
NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_counts_from_now_when_no_subscription() -> None:
    assert compute_expiry(NOW, MONTH, None) == NOW + timedelta(days=30)


def test_extends_active_subscription() -> None:
    current = NOW + timedelta(days=10)
    assert compute_expiry(NOW, DAY, current) == current + timedelta(days=1)


def test_counts_from_now_when_expired() -> None:
    past = NOW - timedelta(days=5)
    assert compute_expiry(NOW, DAY, past) == NOW + timedelta(days=1)
