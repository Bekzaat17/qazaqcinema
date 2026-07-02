"""Оплата: старт (реквизиты/инвойс) и приём чека Kaspi на модерацию.

`initiate` выбирает `PaymentProvider` по способу (Strategy) и отдаёт инструкцию, что
показать пользователю. `submit_proof` (Kaspi) принимает скриншот чека: подтверждает
приём пользователю (и тем же send получает telegram `file_id`), заводит
`PaymentRequest(PENDING)`, переводит юзера в `PENDING_REVIEW` и отправляет чек админам
с кнопками ✅/❌.

Подписку тут НЕ активируем — только после одобрения модератором (moderation →
`PaymentModerationService` → `SubscriptionService.activate`, см. CLAUDE.md: «не
размазывать активацию по платёжным хендлерам»).
"""

from __future__ import annotations

from collections.abc import Mapping

from app.application.ports.payments import PaymentInstruction, PaymentProvider
from app.application.ports.repositories import PaymentRepository, UserRepository
from app.application.ports.telegram import TelegramNotifier
from app.domain.entities.enums import PaymentMethod, PaymentStatus, UserStatus
from app.domain.entities.subscription import PaymentRequest
from app.domain.entities.user import User
from app.domain.tariffs.catalog import get_tariff


class PaymentError(Exception):
    """Ошибка оплаты уровня приложения; презентация мапит её в 4xx."""


class UnknownTariffError(PaymentError):
    """Тариф с таким slug не существует."""


class UnsupportedMethodError(PaymentError):
    """Для способа оплаты не зарегистрирован провайдер."""


_PROOF_ACK_KK = "🧾 Чегіңіз қабылданды. 10–15 минут ішінде тексеріп, жазылымды ашамыз."


class PaymentService:
    def __init__(
        self,
        providers: Mapping[PaymentMethod, PaymentProvider],
        payments: PaymentRepository,
        users: UserRepository,
        notifier: TelegramNotifier,
    ) -> None:
        self._providers = providers
        self._payments = payments
        self._users = users
        self._notifier = notifier

    async def initiate(
        self, user_id: int, tariff_slug: str, method: PaymentMethod
    ) -> PaymentInstruction:
        """Вернуть инструкцию по оплате (реквизиты Kaspi / ссылку инвойса Stars)."""
        tariff = get_tariff(tariff_slug)
        if tariff is None:
            raise UnknownTariffError(tariff_slug)
        provider = self._providers.get(method)
        if provider is None:
            raise UnsupportedMethodError(method.value)
        return await provider.initiate(user_id, tariff)

    async def submit_proof(
        self, user: User, tariff_slug: str, proof: bytes
    ) -> PaymentRequest:
        """Принять чек Kaspi: подтвердить юзеру, завести заявку, уведомить админов.

        Порядок важен: сначала подтверждаем приём (получаем `file_id`) и уведомляем
        админов, и лишь потом переводим юзера в `PENDING_REVIEW` — чтобы фронтовый
        баннер «на проверке» не завис, если уведомление админам не прошло.
        """
        tariff = get_tariff(tariff_slug)
        if tariff is None:
            raise UnknownTariffError(tariff_slug)

        file_id = await self._notifier.acknowledge_payment_proof(
            user.telegram_id, proof, _PROOF_ACK_KK
        )
        request = await self._payments.add(
            PaymentRequest(
                user_id=user.telegram_id,
                tariff=tariff.slug,
                method=PaymentMethod.KASPI,
                status=PaymentStatus.PENDING,
                proof_file_id=file_id,
            )
        )
        assert request.id is not None  # репозиторий проставляет id при вставке
        await self._notifier.send_payment_proof_to_admins(
            request_id=request.id,
            user_id=user.telegram_id,
            username=user.username,
            tariff_title=tariff.title_kk,
            proof_file_id=file_id,
        )
        user.status = UserStatus.PENDING_REVIEW
        await self._users.upsert(user)
        return request
