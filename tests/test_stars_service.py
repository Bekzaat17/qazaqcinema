"""Юнит-тесты StarsPaymentService на фейках (без БД и aiogram).

Проверяем связку Stars с Фазой 6: successful_payment активирует/продлевает подписку
(реальный SubscriptionService на фейках), пишет PaymentRequest(STARS, APPROVED); битый
payload/неизвестный тариф → False без эффектов; заводим юзера, если платёж без /start.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.application.services.stars_service import StarsPaymentService, parse_payload
from app.application.services.subscription_service import SubscriptionService
from app.domain.entities.enums import PaymentMethod, PaymentStatus, UserStatus
from app.domain.entities.subscription import PaymentRequest
from app.domain.entities.user import User

_NOW = datetime(2026, 7, 2, tzinfo=UTC)


class _FakeUsers:
    def __init__(self, user: User | None) -> None:
        self._user = user
        self.upserted: list[User] = []

    async def get(self, telegram_id: int) -> User | None:
        if self._user is not None and self._user.telegram_id == telegram_id:
            return self._user
        return None

    async def upsert(self, user: User) -> User:
        self.upserted.append(user)
        return user

    async def list_expired(self, now: datetime) -> list[User]:
        return []


class _FakePayments:
    def __init__(self) -> None:
        self.added: list[PaymentRequest] = []

    async def add(self, request: PaymentRequest) -> PaymentRequest:
        request.id = len(self.added) + 1
        self.added.append(request)
        return request


class _FakeNotifier:
    def __init__(self) -> None:
        self.user_messages: list[tuple[int, str]] = []

    async def notify_user(self, telegram_id: int, text: str) -> None:
        self.user_messages.append((telegram_id, text))


def _build(
    user: User | None,
) -> tuple[StarsPaymentService, _FakeUsers, _FakePayments, _FakeNotifier]:
    users = _FakeUsers(user)
    payments = _FakePayments()
    notifier = _FakeNotifier()
    subscription = SubscriptionService(users, notifier)  # type: ignore[arg-type]
    service = StarsPaymentService(users, payments, subscription)  # type: ignore[arg-type]
    return service, users, payments, notifier


def test_parse_payload_valid_and_invalid() -> None:
    assert parse_payload("42:1_month") == (42, "1_month")
    assert parse_payload("garbage") is None
    assert parse_payload("abc:1_day") is None
    assert parse_payload("42:") is None


def test_resolve_tariff() -> None:
    service, *_ = _build(None)
    tariff = service.resolve_tariff("42:1_month")
    assert tariff is not None and tariff.slug == "1_month"
    assert service.resolve_tariff("42:nope") is None


async def test_confirm_activates_subscription_for_existing_user() -> None:
    user = User(telegram_id=42, status=UserStatus.NEW)
    service, users, payments, notifier = _build(user)

    ok = await service.confirm(42, "42:1_month", "CHARGE_123", _NOW)

    assert ok is True
    # заявка STARS/APPROVED с id платежа
    assert payments.added and payments.added[0].method is PaymentMethod.STARS
    assert payments.added[0].status is PaymentStatus.APPROVED
    assert payments.added[0].external_charge_id == "CHARGE_123"
    # подписка активна (через SubscriptionService.activate) на 30 дней + DM юзеру
    assert users.upserted and users.upserted[-1].status is UserStatus.ACTIVE
    assert users.upserted[-1].expires_at == _NOW + timedelta(days=30)
    assert notifier.user_messages and notifier.user_messages[0][0] == 42


async def test_confirm_creates_user_when_missing() -> None:
    service, users, _, _ = _build(None)  # платёж без предварительного /start

    ok = await service.confirm(77, "77:1_day", "CHARGE_9", _NOW)

    assert ok is True
    assert users.upserted and users.upserted[-1].telegram_id == 77
    assert users.upserted[-1].status is UserStatus.ACTIVE
    assert users.upserted[-1].expires_at == _NOW + timedelta(days=1)


async def test_confirm_bad_payload_returns_false_without_side_effects() -> None:
    service, users, payments, notifier = _build(User(telegram_id=42))

    ok = await service.confirm(42, "garbage", "CHARGE", _NOW)

    assert ok is False
    assert payments.added == []
    assert users.upserted == []
    assert notifier.user_messages == []


async def test_confirm_unknown_tariff_returns_false() -> None:
    service, _, payments, _ = _build(User(telegram_id=42))

    ok = await service.confirm(42, "42:nope", "CHARGE", _NOW)

    assert ok is False
    assert payments.added == []
