from __future__ import annotations

from app.domain.analytics.percent import change, share


def test_share_computes_rounded_percent() -> None:
    assert share(1, 3) == 33
    assert share(3, 3) == 100


def test_share_is_none_for_empty_denominator() -> None:
    # Нечего делить — молчим, а не врём про «0%».
    assert share(0, 0) is None


def test_change_computes_signed_percent() -> None:
    assert change(15, 10) == 50
    assert change(5, 10) == -50
    assert change(10, 10) == 0


def test_change_is_none_when_previous_is_zero() -> None:
    # Относительное изменение от нуля не определено — не «+∞%».
    assert change(5, 0) is None
