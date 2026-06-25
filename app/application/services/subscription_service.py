"""Жизненный цикл подписки: заявка → модерация → активация/отказ → истечение.

Расчёт срока — чистая функция domain/subscription/expiry.compute_expiry.
"""

from __future__ import annotations

from datetime import datetime

from app.application.ports.repositories import (
    PaymentRepository,
    UserRepository,
)
from app.application.ports.telegram import TelegramNotifier
from app.domain.entities.enums import PaymentMethod
from app.domain.entities.subscription import PaymentRequest


class SubscriptionService:
    def __init__(
        self,
        users: UserRepository,
        payments: PaymentRepository,
        notifier: TelegramNotifier,
    ) -> None:
        self._users = users
        self._payments = payments
        self._notifier = notifier

    async def submit_proof(
        self,
        user_id: int,
        username: str | None,
        tariff_slug: str,
        method: PaymentMethod,
        proof_file_id: str,
    ) -> PaymentRequest:
        """Kaspi: принять чек → PaymentRequest(PENDING), юзер → PENDING_REVIEW,
        переслать чек в чат модерации (кнопки ✅/❌)."""
        raise NotImplementedError

    async def approve(self, request_id: int, now: datetime) -> None:
        """Одобрить заявку: статус APPROVED, рассчитать expires_at (compute_expiry),
        юзер → ACTIVE, уведомить юзера в ЛС."""
        raise NotImplementedError

    async def reject(self, request_id: int, now: datetime) -> None:
        """Отклонить заявку: статус REJECTED, вернуть статус юзера, уведомить в ЛС."""
        raise NotImplementedError

    async def expire_due(self, now: datetime) -> int:
        """Фоновая задача: перевести просроченных ACTIVE → EXPIRED. Вернуть кол-во."""
        raise NotImplementedError
