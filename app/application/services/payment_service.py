"""Оплата: старт (реквизиты/инвойс) и приём чека Kaspi.

`initiate` выбирает `PaymentProvider` по способу (Strategy) и отдаёт инструкцию, что
показать пользователю. `submit_proof` (Kaspi) принимает чек — картинку (скриншот) или
PDF (чек из Kaspi): подтверждает приём пользователю (и тем же send получает telegram
`file_id` + тип медиа в `ProofRef`), заводит `PaymentRequest(PENDING)` и отправляет чек
админам с кнопками ✅/❌.

⚠️ Доступ открывается СРАЗУ, не дожидаясь модератора: админы не круглосуточны, и чек,
присланный ночью, иначе лежал бы до утра — человек заплатил и смотрит на пэйволл.
Модерация после этого работает как отзыв: ✅ ничего не меняет, ❌ забирает доступ
(`PaymentModerationService`). Выдача идёт через `SubscriptionService.activate` — способ
оплаты только зовёт единую точку гранта, своей активации у него нет.

Исключение — человек, у которого уже `REJECT_LIMIT` отклонённых чеков: его заявка идёт
прежним путём (`PENDING_REVIEW`, решает админ). Без этого правила отказ не значил бы
ничего — тот же скриншот заливается снова, и доступ снова открыт.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from app.application.ports.payments import PaymentInstruction, PaymentProvider
from app.application.ports.repositories import PaymentRepository, UserRepository
from app.application.ports.telegram import TelegramNotifier
from app.application.services.subscription_service import SubscriptionService
from app.domain.entities.enums import PaymentMethod, PaymentStatus, UserStatus
from app.domain.entities.subscription import PaymentRequest
from app.domain.entities.user import User
from app.domain.errors import AppError
from app.domain.tariffs.catalog import get_tariff


class PaymentError(AppError):
    """Ошибка оплаты уровня приложения; презентация мапит её в 4xx."""


class UnknownTariffError(PaymentError):
    """Тариф с таким slug не существует."""


class UnsupportedMethodError(PaymentError):
    """Для способа оплаты не зарегистрирован провайдер."""


# Сколько отклонённых чеков в истории закрывают мгновенный доступ. Данные, не логика:
# ужесточить — правка числа. Три, а не один: первый отказ бывает и честной ошибкой
# (не тот файл, не та сумма), а вот третий — это уже система.
REJECT_LIMIT = 3

_PROOF_ACK_KK = "🧾 Чек қабылданды — қолжетімділік бірден ашылды."
# Тому, кому уже трижды отказывали, честно объясняем, почему у него всё по-старому:
# молчаливое ожидание он прочитает как поломку и пойдёт в поддержку.
_PROOF_ACK_MANUAL_KK = (
    "🧾 Чегіңіз қабылданды.\n"
    f"Бұрын {REJECT_LIMIT} төлеміңіз расталмағандықтан, бұл чекті әкімші қолмен "
    "тексереді — нәтижесін хабарлаймыз."
)


class PaymentService:
    def __init__(
        self,
        providers: Mapping[PaymentMethod, PaymentProvider],
        payments: PaymentRepository,
        users: UserRepository,
        notifier: TelegramNotifier,
        subscription: SubscriptionService,
    ) -> None:
        self._providers = providers
        self._payments = payments
        self._users = users
        self._notifier = notifier
        self._subscription = subscription

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
        self,
        user: User,
        tariff_slug: str,
        proof: bytes,
        now: datetime,
        *,
        filename: str,
        content_type: str,
    ) -> PaymentRequest:
        """Принять чек Kaspi: открыть доступ, завести заявку, уведомить админов.

        `filename`/`content_type` — чек может быть картинкой (скриншот) или PDF (чек из
        Kaspi); нотификатор по ним решит, слать photo или document.

        Порядок намеренный: подтверждаем приём (и тем же вызовом получаем `ProofRef`) →
        заводим заявку → отдаём её админам → и только потом открываем доступ. Уведомление
        админов идёт ДО выдачи, потому что доступ без карточки в админ-чате никто не
        отзовёт: чек, о котором не узнали, проверить некому.
        """
        tariff = get_tariff(tariff_slug)
        if tariff is None:
            raise UnknownTariffError(tariff_slug)

        instant = await self._payments.count_rejected(user.telegram_id) < REJECT_LIMIT
        proof_ref = await self._notifier.acknowledge_payment_proof(
            user.telegram_id,
            proof,
            _PROOF_ACK_KK if instant else _PROOF_ACK_MANUAL_KK,
            filename=filename,
            content_type=content_type,
        )
        request = await self._payments.add(
            PaymentRequest(
                user_id=user.telegram_id,
                tariff=tariff.slug,
                method=PaymentMethod.KASPI,
                status=PaymentStatus.PENDING,
                proof_file_id=proof_ref.file_id,
            )
        )
        assert request.id is not None  # репозиторий проставляет id при вставке
        await self._notifier.send_payment_proof_to_admins(
            request_id=request.id,
            user_id=user.telegram_id,
            username=user.username,
            tariff_title=tariff.title_kk,
            proof=proof_ref,
            access_open=instant,
        )
        if not instant:
            user.status = UserStatus.PENDING_REVIEW
            await self._users.upsert(user)
            return request
        await self._subscription.activate(user, tariff, now)
        await self._payments.mark_granted(request.id, now)
        request.granted_at = now
        return request
