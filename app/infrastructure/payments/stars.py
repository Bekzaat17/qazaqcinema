"""Telegram Stars (XTR) — нативная оплата цифрового контента, в т.ч. авто-подписка.

Stars-подписки рекуррентные, но только помесячные (период ≈30 дней). Разовые
покупки (1 день / 3 месяца) — обычные Stars-инвойсы без авто-продления.
Скелет: реализация инвойса — по PLAN (фаза «оплата»), сверившись с актуальной
докой Telegram Payments.
"""

from __future__ import annotations

from app.application.ports.payments import PaymentInstruction
from app.domain.entities.enums import PaymentMethod
from app.domain.tariffs.tariff import Tariff


class TelegramStarsProvider:
    method = PaymentMethod.STARS

    async def initiate(self, user_id: int, tariff: Tariff) -> PaymentInstruction:
        # PLAN: bot.create_invoice_link(currency="XTR", prices=[LabeledPrice(...)],
        # subscription_period=2592000 для recurring) → вернуть invoice_url/payload.
        raise NotImplementedError
