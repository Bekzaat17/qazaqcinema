"""Юнит-тесты PaymentService на фейках (без БД, aiogram и HTTP).

Проверяем: initiate отдаёт инструкцию Kaspi и валидирует тариф/способ; submit_proof
заводит PENDING-заявку с file_id из подтверждения, уведомляет админов и ОТКРЫВАЕТ
доступ сразу; человек с `REJECT_LIMIT` отказов идёт прежним путём (PENDING_REVIEW);
при неизвестном тарифе — падает ДО побочных эффектов.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.application.ports.payments import PaymentInstruction
from app.application.ports.telegram import ProofRef
from app.application.services.payment_service import (
    REJECT_LIMIT,
    PaymentService,
    UnknownTariffError,
    UnsupportedMethodError,
)
from app.domain.entities.enums import PaymentMethod, PaymentStatus, UserStatus
from app.domain.entities.subscription import PaymentRequest
from app.domain.entities.user import User
from app.domain.tariffs.catalog import get_tariff
from app.domain.tariffs.tariff import Tariff

MONTH = get_tariff("1_month")
assert MONTH is not None
_NOW = datetime(2026, 6, 29, tzinfo=UTC)


class _FakeKaspiProvider:
    method = PaymentMethod.KASPI

    async def initiate(self, user_id: int, tariff: Tariff) -> PaymentInstruction:
        return PaymentInstruction(
            method=PaymentMethod.KASPI,
            kaspi_number="87010000000",
            kaspi_name="QazaqCinema",
            payload=f"{user_id}:{tariff.slug}",
        )


class _FakePayments:
    def __init__(self, rejected: int = 0) -> None:
        self.added: list[PaymentRequest] = []
        self.granted: list[tuple[int, datetime]] = []
        self._rejected = rejected

    async def add(self, request: PaymentRequest) -> PaymentRequest:
        request.id = len(self.added) + 1
        self.added.append(request)
        return request

    async def mark_granted(self, request_id: int, at: datetime) -> None:
        self.granted.append((request_id, at))

    async def count_rejected(self, user_id: int) -> int:
        return self._rejected


class _FakeUsers:
    def __init__(self) -> None:
        self.upserted: list[User] = []

    async def upsert(self, user: User) -> User:
        self.upserted.append(user)
        return user


class _FakeNotifier:
    def __init__(self) -> None:
        self.ack: list[tuple[int, bytes, str, str, str]] = []
        self.admin: list[tuple[int, int, str | None, str, ProofRef, bool]] = []

    async def acknowledge_payment_proof(
        self, telegram_id: int, proof: bytes, caption: str, *, filename: str, content_type: str
    ) -> ProofRef:
        self.ack.append((telegram_id, proof, caption, filename, content_type))
        return ProofRef("PROOF_FILE_ID", is_document=content_type == "application/pdf")

    async def send_payment_proof_to_admins(
        self,
        *,
        request_id: int,
        user_id: int,
        username: str | None,
        tariff_title: str,
        proof: ProofRef,
        access_open: bool,
    ) -> None:
        self.admin.append((request_id, user_id, username, tariff_title, proof, access_open))


class _FakeSubscription:
    """Фейк `SubscriptionService`: важен сам факт вызова единой точки гранта."""

    def __init__(self) -> None:
        self.activated: list[tuple[int, str, datetime]] = []

    async def activate(self, user: User, tariff: Tariff, now: datetime) -> User:
        self.activated.append((user.telegram_id, tariff.slug, now))
        user.status = UserStatus.ACTIVE
        user.expires_at = now + tariff.duration
        return user


def _service(
    providers: dict[PaymentMethod, _FakeKaspiProvider] | None = None,
    rejected: int = 0,
) -> tuple[PaymentService, _FakePayments, _FakeUsers, _FakeNotifier, _FakeSubscription]:
    payments = _FakePayments(rejected)
    users = _FakeUsers()
    notifier = _FakeNotifier()
    subscription = _FakeSubscription()
    if providers is None:
        providers = {PaymentMethod.KASPI: _FakeKaspiProvider()}
    service = PaymentService(providers, payments, users, notifier, subscription)  # type: ignore[arg-type]
    return service, payments, users, notifier, subscription


async def test_initiate_returns_kaspi_instruction() -> None:
    service, *_ = _service()

    instruction = await service.initiate(42, "1_month", PaymentMethod.KASPI)

    assert instruction.method is PaymentMethod.KASPI
    assert instruction.kaspi_number == "87010000000"
    assert instruction.payload == "42:1_month"


async def test_initiate_unknown_tariff_raises() -> None:
    service, *_ = _service()

    with pytest.raises(UnknownTariffError):
        await service.initiate(42, "nope", PaymentMethod.KASPI)


async def test_initiate_unsupported_method_raises() -> None:
    # В карте только Kaspi — запрос Stars должен упасть (провайдер не зарегистрирован).
    service, *_ = _service(providers={PaymentMethod.KASPI: _FakeKaspiProvider()})

    with pytest.raises(UnsupportedMethodError):
        await service.initiate(42, "1_month", PaymentMethod.STARS)


async def test_submit_proof_opens_access_immediately() -> None:
    service, payments, _users, notifier, subscription = _service()
    user = User(telegram_id=42, username="beka", status=UserStatus.NEW)

    request = await service.submit_proof(
        user, "1_month", b"jpegbytes", _NOW, filename="proof.jpg", content_type="image/jpeg"
    )

    # заявка PENDING с file_id, полученным при подтверждении приёма
    assert request.status is PaymentStatus.PENDING
    assert request.method is PaymentMethod.KASPI
    assert request.proof_file_id == "PROOF_FILE_ID"
    assert payments.added and payments.added[0].tariff == "1_month"
    # доступ открыт СЕЙЧАС, через единую точку гранта, и это отмечено на заявке
    assert subscription.activated == [(42, "1_month", _NOW)]
    assert payments.granted == [(request.id, _NOW)]
    assert request.granted_at == _NOW
    # чек ушёл админам с id заявки, казахским названием тарифа и признаком «доступ открыт»
    assert notifier.admin and notifier.admin[0][0] == request.id
    assert MONTH is not None
    assert notifier.admin[0][3] == MONTH.title_kk
    assert notifier.admin[0][5] is True
    # картинка → шлётся как photo (не document)
    assert notifier.admin[0][4].is_document is False


async def test_submit_proof_after_reject_limit_waits_for_admin() -> None:
    """Трижды отклонённый чек больше не открывает доступ сам — иначе отказ ничего не значит."""
    service, payments, users, notifier, subscription = _service(rejected=REJECT_LIMIT)
    user = User(telegram_id=42, username="beka", status=UserStatus.EXPIRED)

    request = await service.submit_proof(
        user, "1_month", b"jpegbytes", _NOW, filename="proof.jpg", content_type="image/jpeg"
    )

    assert subscription.activated == []
    assert payments.granted == []
    assert request.granted_at is None
    assert users.upserted and users.upserted[-1].status is UserStatus.PENDING_REVIEW
    # админам видно, что доступ НЕ открыт: их решение тут выдаёт подписку, а не отбирает
    assert notifier.admin[0][5] is False
    # человеку объяснили, почему он ждёт, а не получил доступ сразу
    assert str(REJECT_LIMIT) in notifier.ack[0][2]


async def test_submit_proof_pdf_is_sent_as_document() -> None:
    # Kaspi отдаёт чек PDF-файлом → нотификатор должен пометить его документом,
    # чтобы и юзеру, и админам он ушёл через send_document, а не send_photo.
    service, _payments, _users, notifier, _subscription = _service()
    user = User(telegram_id=42, username="beka", status=UserStatus.NEW)

    await service.submit_proof(
        user, "1_month", b"%PDF-1.4", _NOW, filename="kaspi.pdf", content_type="application/pdf"
    )

    assert notifier.admin and notifier.admin[0][4].is_document is True


async def test_submit_proof_unknown_tariff_raises_before_side_effects() -> None:
    service, payments, users, notifier, subscription = _service()
    user = User(telegram_id=42, status=UserStatus.NEW)

    with pytest.raises(UnknownTariffError):
        await service.submit_proof(
            user, "nope", b"x", _NOW, filename="proof.jpg", content_type="image/jpeg"
        )

    assert payments.added == []
    assert users.upserted == []
    assert notifier.ack == []
    assert subscription.activated == []
