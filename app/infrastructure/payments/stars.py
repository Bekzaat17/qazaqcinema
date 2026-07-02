"""Telegram Stars (XTR) — нативная оплата цифрового контента, в т.ч. авто-подписка.

`initiate` создаёт invoice-ссылку через `Bot.create_invoice_link`. Помесячный тариф
(`recurring=True`) уходит подпиской с `subscription_period` (Telegram разрешает только
30 дней = 2592000 c); разовый (`1_day`) — обычным Stars-инвойсом. Оплата подтверждается
уже на стороне бота (`pre_checkout_query` → `successful_payment` → `StarsPaymentService`).

Сверено с докой Telegram (payments-stars): валюта — `XTR`; для Stars `provider_token`
пустой; XTR без дробной части — `amount` = число звёзд напрямую (не ×100).
"""

from __future__ import annotations

from aiogram import Bot
from aiogram.types import LabeledPrice

from app.application.ports.payments import PaymentInstruction
from app.domain.entities.enums import PaymentMethod
from app.domain.tariffs.tariff import Tariff

# Единственный допустимый период Stars-подписки — 30 дней (см. createInvoiceLink).
STARS_SUBSCRIPTION_PERIOD = 30 * 24 * 60 * 60  # 2592000 c


def build_payload(user_id: int, tariff: Tariff) -> str:
    """Payload инвойса — как в Kaspi: `<user_id>:<slug>` (вернётся в successful_payment)."""
    return f"{user_id}:{tariff.slug}"


class TelegramStarsProvider:
    method = PaymentMethod.STARS

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def initiate(self, user_id: int, tariff: Tariff) -> PaymentInstruction:
        payload = build_payload(user_id, tariff)
        prices = [LabeledPrice(label=tariff.title_kk, amount=tariff.price_xtr)]
        # recurring-тариф → авто-подписка (subscription_period); разовый → None.
        subscription_period = STARS_SUBSCRIPTION_PERIOD if tariff.recurring else None
        link = await self._bot.create_invoice_link(
            title=f"QazaqCinema — {tariff.title_kk}",
            description="Қазақша дубляждағы сирек мультфильмдер мен анимеге қолжетімділік.",
            payload=payload,
            currency="XTR",
            prices=prices,
            provider_token="",  # для Telegram Stars — пусто
            subscription_period=subscription_period,
        )
        return PaymentInstruction(
            method=PaymentMethod.STARS,
            invoice_url=link,
            payload=payload,
        )
