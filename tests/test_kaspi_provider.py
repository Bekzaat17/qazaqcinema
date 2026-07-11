"""Юнит-тест KaspiManualProvider: способ перевода включается заполненностью env.

Контракт («оплата — данные»): PAY_KASPI_NUMBER → перевод по номеру, PAY_KASPI_LINK →
оплата по ссылке. Пустой параметр → соответствующее поле `None` (фронт скрывает способ).
Заданы оба → доступны оба; задан один — только он.
"""

from __future__ import annotations

from app.domain.entities.enums import PaymentMethod
from app.domain.tariffs.catalog import get_tariff
from app.infrastructure.payments.kaspi import KaspiManualProvider

MONTH = get_tariff("1_month")
assert MONTH is not None


async def test_both_number_and_link_available() -> None:
    provider = KaspiManualProvider("87010000000", "QazaqCinema", "https://pay.kaspi.kz/pay/x")

    instruction = await provider.initiate(42, MONTH)

    assert instruction.method is PaymentMethod.KASPI
    assert instruction.kaspi_number == "87010000000"
    assert instruction.kaspi_name == "QazaqCinema"
    assert instruction.kaspi_link == "https://pay.kaspi.kz/pay/x"
    assert instruction.payload == "42:1_month"


async def test_number_only_hides_link() -> None:
    provider = KaspiManualProvider("87010000000", "QazaqCinema", "")

    instruction = await provider.initiate(42, MONTH)

    assert instruction.kaspi_number == "87010000000"
    assert instruction.kaspi_name == "QazaqCinema"
    assert instruction.kaspi_link is None


async def test_link_only_hides_number() -> None:
    provider = KaspiManualProvider("", "", "https://pay.kaspi.kz/pay/x")

    instruction = await provider.initiate(42, MONTH)

    assert instruction.kaspi_link == "https://pay.kaspi.kz/pay/x"
    assert instruction.kaspi_number is None
    assert instruction.kaspi_name is None
