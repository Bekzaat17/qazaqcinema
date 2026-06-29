"""Движок доступа: единая точка гранта/ревока подписки.

Это ядро Фазы 6 — ДО любой оплаты. Способы оплаты (Kaspi-модерация, Telegram Stars)
не активируют подписку сами, а лишь вызывают `activate` (см. CLAUDE.md: «не размазывать
активацию по платёжным хендлерам»). Заведение PaymentRequest и модерация — это Фаза 7,
её хендлер на одобрение дёргает тот же `activate`.

Расчёт срока — чистая функция `domain/subscription/expiry.compute_expiry`
(продлевает активную подписку, иначе считает от now).
"""

from __future__ import annotations

from datetime import datetime

from app.application.ports.repositories import UserRepository
from app.application.ports.telegram import TelegramNotifier
from app.domain.entities.enums import UserStatus
from app.domain.entities.user import User
from app.domain.subscription.expiry import compute_expiry
from app.domain.tariffs.tariff import Tariff


class SubscriptionService:
    def __init__(self, users: UserRepository, notifier: TelegramNotifier) -> None:
        self._users = users
        self._notifier = notifier

    async def activate(self, user: User, tariff: Tariff, now: datetime) -> User:
        """Грант подписки: рассчитать срок, перевести юзера в ACTIVE, сохранить, уведомить.

        Идемпотентна по эффекту: повторный вызов с активной подпиской — продлевает
        (compute_expiry считает от текущего `expires_at`), а не сбрасывает срок.
        """
        user.expires_at = compute_expiry(now, tariff, user.expires_at)
        user.status = UserStatus.ACTIVE
        user.selected_tariff = tariff.slug
        saved = await self._users.upsert(user)
        await self._notifier.notify_user(
            user.telegram_id,
            "✅ Жазылым белсендірілді!\n"
            f"Тариф: {tariff.title_kk}\n"
            f"Қолжетімді: {user.expires_at:%d.%m.%Y %H:%M} (UTC) дейін",
        )
        return saved

    async def expire_due(self, now: datetime) -> int:
        """Фоновая задача: ACTIVE с истёкшим `expires_at` → EXPIRED. Вернуть кол-во.

        Списком из репозитория (`list_expired`), без побочной выдачи видео — гейт доступа
        и так читает `has_active_access`, эта задача лишь приводит хранимый статус в порядок.
        """
        expired = await self._users.list_expired(now)
        for user in expired:
            user.status = UserStatus.EXPIRED
            await self._users.upsert(user)
        return len(expired)
