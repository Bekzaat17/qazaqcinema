from __future__ import annotations

from datetime import timedelta

from app.domain.tariffs.catalog import all_tariffs, get_tariff


def test_two_tariffs_present() -> None:
    assert {t.slug for t in all_tariffs()} == {"1_day", "1_month"}


def test_prices_match_prd() -> None:
    assert get_tariff("1_day").price_kzt == 290  # type: ignore[union-attr]
    assert get_tariff("1_month").price_kzt == 1290  # type: ignore[union-attr]


def test_star_prices_match_prd() -> None:
    # Звёзды — премия ~25% к тенге, округлённая вверх до полусотни (курс ≈9.6 ₸/звезда).
    assert get_tariff("1_day").price_xtr == 50  # type: ignore[union-attr]
    assert get_tariff("1_month").price_xtr == 200  # type: ignore[union-attr]


def test_durations() -> None:
    assert get_tariff("1_day").duration == timedelta(days=1)  # type: ignore[union-attr]
    assert get_tariff("1_month").duration == timedelta(days=30)  # type: ignore[union-attr]


def test_only_monthly_is_recurring() -> None:
    assert get_tariff("1_month").recurring is True  # type: ignore[union-attr]
    assert get_tariff("1_day").recurring is False  # type: ignore[union-attr]


def test_unknown_tariff_is_none() -> None:
    assert get_tariff("does_not_exist") is None
