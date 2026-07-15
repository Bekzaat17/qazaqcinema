"""Движок доступа: единая точка гранта/ревока подписки.

Это ядро Фазы 6 — ДО любой оплаты. Способы оплаты (Kaspi-модерация, Telegram Stars)
не активируют подписку сами, а лишь вызывают `activate` (см. CLAUDE.md: «не размазывать
активацию по платёжным хендлерам»). Заведение PaymentRequest и модерация — это Фаза 7,
её хендлер на одобрение дёргает тот же `activate`.

Расчёт срока — чистая функция `domain/subscription/expiry.compute_expiry`
(продлевает активную подписку, иначе считает от now).
"""

from __future__ import annotations

import logging
from datetime import datetime

from app.application.ports.repositories import UserRepository
from app.application.ports.telegram import TelegramNotifier
from app.application.services.video_retention_service import VideoRetentionService
from app.domain.entities.enums import UserStatus
from app.domain.entities.user import User
from app.domain.subscription.expiry import compute_expiry
from app.domain.tariffs.tariff import Tariff

logger = logging.getLogger(__name__)

_EXPIRED_DM_KK = (
    "⌛️ Жазылым мерзімі аяқталды.\n"
    "Қайта жалғастыру үшін төмендегі «🎬 Кинотеатр» батырмасынан тариф таңдаңыз."
)


class SubscriptionService:
    def __init__(
        self,
        users: UserRepository,
        notifier: TelegramNotifier,
        retention: VideoRetentionService,
    ) -> None:
        self._users = users
        self._notifier = notifier
        self._retention = retention

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

        На переходе ACTIVE→EXPIRED также: (1) уведомляем юзера, что подписка кончилась,
        и (2) забираем выданные видео (`VideoRetentionService.purge_for_user`) — оплаченный
        контент не остаётся на руках. Продлил подписку — заново жмёт «Көру» и получает опять.

        Обе побочки — best-effort и КАЖДАЯ в своём try/except: юзер тут уже сохранён как
        EXPIRED, а `list_expired` фильтрует по ACTIVE — значит сбой побочки после upsert
        не повторится никогда (второго шанса не будет). Поэтому сбой одного юзера не должен
        уносить с собой ни остальных, ни сам факт гашения статуса.

        Заметь: доступ пропадает НЕ здесь. `has_active_access` считает `expires_at > now` в
        реальном времени на каждом запросе → 403 приходит секунда-в-секунду. Этот джоб лишь
        проставляет статус, уведомляет и чистит видео.
        """
        expired = await self._users.list_expired(now)
        for user in expired:
            user.status = UserStatus.EXPIRED
            await self._users.upsert(user)
            await self._notify_expired(user.telegram_id)
            await self._purge_deliveries(user.telegram_id)
        return len(expired)

    async def _notify_expired(self, telegram_id: int) -> None:
        # Best-effort DM: юзер мог заблокировать бота — не роняем фоновую задачу из-за этого.
        try:
            await self._notifier.notify_user(telegram_id, _EXPIRED_DM_KK)
        except Exception:
            logger.warning("Не удалось уведомить %s об истечении подписки", telegram_id)

    async def _purge_deliveries(self, user_id: int) -> None:
        # Тоже под try/except: сеть/Telegram могут сорваться, а юзер уже EXPIRED → сюда
        # он больше не попадёт. Пусть его видео дочистит ежечасный purge_stale (≤40 ч),
        # чем один сбой оборвёт гашение остальных.
        try:
            await self._retention.purge_for_user(user_id)
        except Exception:
            logger.exception("Не удалось удалить видео юзера %s", user_id)
