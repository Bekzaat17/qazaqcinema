"""Юнит-тесты PaymentService на фейках (без БД, aiogram и HTTP).

Проверяем: initiate отдаёт инструкцию Kaspi и валидирует тариф/способ; submit_proof
заводит PENDING-заявку с file_id из подтверждения, уведомляет админов и переводит
юзера в PENDING_REVIEW; при неизвестном тарифе — падает ДО побочных эффектов.
"""

from __future__ import annotations

import pytest
from app.application.ports.payments import PaymentInstruction
from app.application.services.payment_service import (
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
    def __init__(self) -> None:
        self.added: list[PaymentRequest] = []

    async def add(self, request: PaymentRequest) -> PaymentRequest:
        request.id = len(self.added) + 1
        self.added.append(request)
        return request


class _FakeUsers:
    def __init__(self) -> None:
        self.upserted: list[User] = []

    async def upsert(self, user: User) -> User:
        self.upserted.append(user)
        return user


class _FakeNotifier:
    def __init__(self) -> None:
        self.ack: list[tuple[int, bytes, str]] = []
        self.admin: list[tuple[int, int, str | None, str, str]] = []

    async def acknowledge_payment_proof(
        self, telegram_id: int, proof: bytes, caption: str
    ) -> str:
        self.ack.append((telegram_id, proof, caption))
        return "PROOF_FILE_ID"

    async def send_payment_proof_to_admins(
        self,
        request_id: int,
        user_id: int,
        username: str | None,
        tariff_title: str,
        proof_file_id: str,
    ) -> None:
        self.admin.append((request_id, user_id, username, tariff_title, proof_file_id))


def _service(
    providers: dict[PaymentMethod, _FakeKaspiProvider] | None = None,
) -> tuple[PaymentService, _FakePayments, _FakeUsers, _FakeNotifier]:
    payments = _FakePayments()
    users = _FakeUsers()
    notifier = _FakeNotifier()
    if providers is None:
        providers = {PaymentMethod.KASPI: _FakeKaspiProvider()}
    service = PaymentService(providers, payments, users, notifier)  # type: ignore[arg-type]
    return service, payments, users, notifier


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


async def test_submit_proof_creates_pending_and_notifies() -> None:
    service, payments, users, notifier = _service()
    user = User(telegram_id=42, username="beka", status=UserStatus.NEW)

    request = await service.submit_proof(user, "1_month", b"jpegbytes")

    # заявка PENDING с file_id, полученным при подтверждении приёма
    assert request.status is PaymentStatus.PENDING
    assert request.method is PaymentMethod.KASPI
    assert request.proof_file_id == "PROOF_FILE_ID"
    assert payments.added and payments.added[0].tariff == "1_month"
    # юзеру подтвердили приём и перевели в PENDING_REVIEW
    assert notifier.ack and notifier.ack[0][0] == 42
    assert users.upserted and users.upserted[-1].status is UserStatus.PENDING_REVIEW
    # чек ушёл админам с id заявки и казахским названием тарифа
    assert notifier.admin and notifier.admin[0][0] == request.id
    assert MONTH is not None
    assert notifier.admin[0][3] == MONTH.title_kk


async def test_submit_proof_unknown_tariff_raises_before_side_effects() -> None:
    service, payments, users, notifier = _service()
    user = User(telegram_id=42, status=UserStatus.NEW)

    with pytest.raises(UnknownTariffError):
        await service.submit_proof(user, "nope", b"x")

    assert payments.added == []
    assert users.upserted == []
    assert notifier.ack == []
