"""Юнит-тест TelegramStarsProvider на фейковом Bot.

Сверяем критичные параметры Stars-инвойса (в проде их не поймать без реальной оплаты):
валюта XTR, пустой provider_token, amount = число звёзд напрямую, а для помесячного
тарифа — subscription_period 2592000 c (для разового — None).
"""

from __future__ import annotations

from typing import Any

from app.domain.entities.enums import PaymentMethod
from app.domain.tariffs.catalog import get_tariff
from app.infrastructure.payments.stars import (
    STARS_SUBSCRIPTION_PERIOD,
    TelegramStarsProvider,
)

DAY = get_tariff("1_day")
MONTH = get_tariff("1_month")
assert DAY is not None and MONTH is not None


class _FakeBot:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def create_invoice_link(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return "https://t.me/invoice/TEST"


async def test_monthly_tariff_creates_recurring_stars_invoice() -> None:
    bot = _FakeBot()
    provider = TelegramStarsProvider(bot)  # type: ignore[arg-type]

    instruction = await provider.initiate(42, MONTH)

    assert instruction.method is PaymentMethod.STARS
    assert instruction.invoice_url == "https://t.me/invoice/TEST"
    assert instruction.payload == "42:1_month"
    call = bot.calls[0]
    assert call["currency"] == "XTR"
    assert call["provider_token"] == ""
    assert call["subscription_period"] == STARS_SUBSCRIPTION_PERIOD == 2592000
    assert call["prices"][0].amount == MONTH.price_xtr  # amount = число звёзд, без ×100


async def test_daily_tariff_creates_one_time_stars_invoice() -> None:
    bot = _FakeBot()
    provider = TelegramStarsProvider(bot)  # type: ignore[arg-type]

    await provider.initiate(7, DAY)

    call = bot.calls[0]
    assert call["subscription_period"] is None  # разовый тариф — без авто-продления
    assert call["prices"][0].amount == DAY.price_xtr
