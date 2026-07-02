"""Модерация чеков Kaspi: одобрить (→ активация подписки) / отклонить.

Тонкий aiogram-хендлер (`bot/handlers/moderation.py`) парсит callback и вызывает этот
use-case. Грант подписки делегируется `SubscriptionService.activate` — единая точка
Фазы 6, не дублируем. Идемпотентность: обрабатываем ТОЛЬКО `PENDING`-заявку (повторный
клик → `ALREADY_HANDLED`), чтобы одобрение не выдало подписку дважды.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto

from app.application.ports.repositories import PaymentRepository, UserRepository
from app.application.ports.telegram import TelegramNotifier
from app.application.services.subscription_service import SubscriptionService
from app.domain.entities.enums import PaymentStatus, UserStatus
from app.domain.tariffs.catalog import get_tariff


class ModerationOutcome(Enum):
    APPROVED = auto()         # чек одобрен → подписка активирована
    REJECTED = auto()         # чек отклонён → доступа нет
    NOT_FOUND = auto()        # заявки нет или битые данные (нет юзера/тарифа)
    ALREADY_HANDLED = auto()  # заявка уже одобрена/отклонена — повтор игнорируем


@dataclass(slots=True)
class ModerationResult:
    outcome: ModerationOutcome
    user_id: int | None = None
    tariff_title: str | None = None


_REJECT_DM_KK = "❌ Төлеміңіз расталмады. Чекті қайта жіберіп көріңіз немесе қолдауға жазыңыз."


class PaymentModerationService:
    def __init__(
        self,
        payments: PaymentRepository,
        users: UserRepository,
        subscription: SubscriptionService,
        notifier: TelegramNotifier,
    ) -> None:
        self._payments = payments
        self._users = users
        self._subscription = subscription
        self._notifier = notifier

    async def approve(self, request_id: int, now: datetime) -> ModerationResult:
        request = await self._payments.get(request_id)
        if request is None:
            return ModerationResult(ModerationOutcome.NOT_FOUND)
        if request.status is not PaymentStatus.PENDING:
            return ModerationResult(ModerationOutcome.ALREADY_HANDLED)
        tariff = get_tariff(request.tariff)
        user = await self._users.get(request.user_id)
        if tariff is None or user is None:
            return ModerationResult(ModerationOutcome.NOT_FOUND)
        await self._payments.set_status(request_id, PaymentStatus.APPROVED, now)
        # Грант подписки (ACTIVE + expires_at + DM юзеру) — ядро Фазы 6.
        await self._subscription.activate(user, tariff, now)
        return ModerationResult(
            ModerationOutcome.APPROVED,
            user_id=user.telegram_id,
            tariff_title=tariff.title_kk,
        )

    async def reject(self, request_id: int, now: datetime) -> ModerationResult:
        request = await self._payments.get(request_id)
        if request is None:
            return ModerationResult(ModerationOutcome.NOT_FOUND)
        if request.status is not PaymentStatus.PENDING:
            return ModerationResult(ModerationOutcome.ALREADY_HANDLED)
        await self._payments.set_status(request_id, PaymentStatus.REJECTED, now)
        user = await self._users.get(request.user_id)
        if user is not None:
            user.status = UserStatus.EXPIRED  # снять «на проверке» → снова пэйволл
            await self._users.upsert(user)
            await self._notifier.notify_user(user.telegram_id, _REJECT_DM_KK)
        return ModerationResult(ModerationOutcome.REJECTED, user_id=request.user_id)
