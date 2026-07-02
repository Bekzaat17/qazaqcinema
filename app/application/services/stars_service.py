"""Telegram Stars: подтверждение оплаты (pre_checkout) и активация подписки.

Инвойс создаёт провайдер (infra), а подтверждает оплату бот: `pre_checkout_query`
(быстрая валидация payload — без БД, чтобы уложиться в лимит Telegram ~10 c) →
`successful_payment` → `confirm` (запись `PaymentRequest(APPROVED)` + грант через
`SubscriptionService.activate` — Фаза 6, не дублируем). Авто-продление (recurring)
прилетает тем же `successful_payment` и так же продлевает подписку — отдельной ветки нет.

Payload инвойса — `<user_id>:<slug>` (пишет `infrastructure/payments/stars.build_payload`,
читаем здесь `parse_payload`). Слаги без «:» → `partition` устойчив к «_» в слаге.
"""

from __future__ import annotations

from datetime import datetime

from app.application.ports.repositories import PaymentRepository, UserRepository
from app.application.services.subscription_service import SubscriptionService
from app.domain.entities.enums import PaymentMethod, PaymentStatus, UserStatus
from app.domain.entities.subscription import PaymentRequest
from app.domain.entities.user import User
from app.domain.tariffs.catalog import get_tariff
from app.domain.tariffs.tariff import Tariff


def parse_payload(payload: str) -> tuple[int, str] | None:
    user_part, sep, slug = payload.partition(":")
    if not sep or not slug or not user_part.isdigit():
        return None
    return int(user_part), slug


class StarsPaymentService:
    def __init__(
        self,
        users: UserRepository,
        payments: PaymentRepository,
        subscription: SubscriptionService,
    ) -> None:
        self._users = users
        self._payments = payments
        self._subscription = subscription

    def resolve_tariff(self, payload: str) -> Tariff | None:
        """Валидация для pre_checkout: тариф из payload (in-memory, без БД)."""
        parsed = parse_payload(payload)
        if parsed is None:
            return None
        _, slug = parsed
        return get_tariff(slug)

    async def confirm(
        self, payer_id: int, payload: str, charge_id: str, now: datetime
    ) -> bool:
        """successful_payment: записать заявку и активировать/продлить подписку.

        Идентичен для первого платежа и авто-продления (recurring): `activate` продлевает
        от текущего срока. Плательщик — из апдейта (`payer_id`), тариф — из payload.
        Возвращает False при битом payload/неизвестном тарифе.
        """
        tariff = self.resolve_tariff(payload)
        if tariff is None:
            return False
        user = await self._users.get(payer_id)
        if user is None:  # оплатил, но пользователя ещё нет — заводим и грантим
            user = User(telegram_id=payer_id, status=UserStatus.NEW)
        await self._payments.add(
            PaymentRequest(
                user_id=payer_id,
                tariff=tariff.slug,
                method=PaymentMethod.STARS,
                status=PaymentStatus.APPROVED,
                external_charge_id=charge_id,
            )
        )
        await self._subscription.activate(user, tariff, now)
        return True
