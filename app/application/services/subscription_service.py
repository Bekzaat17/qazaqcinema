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

from app.application.ports.repositories import UserRepository, VideoDeliveryRepository
from app.application.ports.telegram import TelegramNotifier
from app.domain.entities.enums import UserStatus
from app.domain.entities.user import User
from app.domain.subscription.expiry import compute_expiry
from app.domain.tariffs.tariff import Tariff


class SubscriptionService:
    def __init__(
        self,
        users: UserRepository,
        notifier: TelegramNotifier,
        deliveries: VideoDeliveryRepository,
    ) -> None:
        self._users = users
        self._notifier = notifier
        self._deliveries = deliveries

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

        На переходе ACTIVE→EXPIRED также удаляем ВСЕ выданные юзеру видео из чата
        (`_purge_deliveries`): подписка кончилась → оплаченный контент не остаётся на
        руках. Удаление best-effort (см. `delete_message`), чтобы «мёртвый» id не сорвал
        гашение статуса. Продлил подписку — заново жмёт «Көру» и получает видео опять.
        """
        expired = await self._users.list_expired(now)
        for user in expired:
            user.status = UserStatus.EXPIRED
            await self._users.upsert(user)
            await self._purge_deliveries(user.telegram_id)
        return len(expired)

    async def _purge_deliveries(self, user_id: int) -> None:
        deliveries = await self._deliveries.list_for_user(user_id)
        for delivery in deliveries:
            await self._notifier.delete_message(delivery.chat_id, delivery.message_id)
        await self._deliveries.clear_for_user(user_id)
