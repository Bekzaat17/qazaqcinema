"""Юнит-тесты PaymentModerationService на фейках (без БД и aiogram).

Проверяем связку Фазы 7 с Фазой 6: одобрение чека активирует подписку (реальный
SubscriptionService на фейковых репозиториях), повторный клик не выдаёт грант дважды,
отклонение снимает «на проверке» и уведомляет юзера.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.application.services.moderation_service import (
    ModerationOutcome,
    PaymentModerationService,
)
from app.application.services.subscription_service import SubscriptionService
from app.domain.entities.enums import PaymentMethod, PaymentStatus, UserStatus
from app.domain.entities.subscription import PaymentRequest
from app.domain.entities.user import User

_NOW = datetime(2026, 7, 2, tzinfo=UTC)


class _FakePayments:
    def __init__(self, request: PaymentRequest | None) -> None:
        self._request = request
        self.status_calls: list[tuple[int, PaymentStatus]] = []

    async def get(self, request_id: int) -> PaymentRequest | None:
        if self._request is not None and self._request.id == request_id:
            return self._request
        return None

    async def set_status(
        self, request_id: int, status: PaymentStatus, reviewed_at: datetime
    ) -> PaymentRequest | None:
        self.status_calls.append((request_id, status))
        if self._request is not None and self._request.id == request_id:
            self._request.status = status
            self._request.reviewed_at = reviewed_at
            return self._request
        return None


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


class _FakeNotifier:
    def __init__(self) -> None:
        self.user_messages: list[tuple[int, str]] = []

    async def notify_user(self, telegram_id: int, text: str) -> None:
        self.user_messages.append((telegram_id, text))


def _pending_request() -> PaymentRequest:
    return PaymentRequest(
        id=1,
        user_id=42,
        tariff="1_month",
        method=PaymentMethod.KASPI,
        status=PaymentStatus.PENDING,
        proof_file_id="F",
    )


def _build(
    request: PaymentRequest | None, user: User | None
) -> tuple[PaymentModerationService, _FakePayments, _FakeUsers, _FakeNotifier]:
    payments = _FakePayments(request)
    users = _FakeUsers(user)
    notifier = _FakeNotifier()
    subscription = SubscriptionService(users, notifier)  # type: ignore[arg-type]
    service = PaymentModerationService(payments, users, subscription, notifier)  # type: ignore[arg-type]
    return service, payments, users, notifier


async def test_approve_activates_subscription() -> None:
    user = User(telegram_id=42, status=UserStatus.PENDING_REVIEW)
    service, payments, users, notifier = _build(_pending_request(), user)

    result = await service.approve(1, _NOW)

    assert result.outcome is ModerationOutcome.APPROVED
    assert payments.status_calls == [(1, PaymentStatus.APPROVED)]
    # подписка активна (через SubscriptionService.activate) с корректным сроком
    assert users.upserted and users.upserted[-1].status is UserStatus.ACTIVE
    assert users.upserted[-1].has_active_access(_NOW)
    assert users.upserted[-1].expires_at == _NOW + timedelta(days=30)
    # активация уведомила юзера
    assert notifier.user_messages and notifier.user_messages[0][0] == 42


async def test_approve_already_handled_does_not_activate() -> None:
    request = _pending_request()
    request.status = PaymentStatus.APPROVED  # уже обработана
    user = User(telegram_id=42, status=UserStatus.ACTIVE)
    service, payments, users, _ = _build(request, user)

    result = await service.approve(1, _NOW)

    assert result.outcome is ModerationOutcome.ALREADY_HANDLED
    assert payments.status_calls == []
    assert users.upserted == []


async def test_approve_not_found() -> None:
    service, _, _, _ = _build(None, None)

    result = await service.approve(999, _NOW)

    assert result.outcome is ModerationOutcome.NOT_FOUND


async def test_reject_marks_no_access_and_notifies() -> None:
    user = User(telegram_id=42, status=UserStatus.PENDING_REVIEW)
    service, payments, users, notifier = _build(_pending_request(), user)

    result = await service.reject(1, _NOW)

    assert result.outcome is ModerationOutcome.REJECTED
    assert payments.status_calls == [(1, PaymentStatus.REJECTED)]
    assert users.upserted and users.upserted[-1].status is UserStatus.EXPIRED
    assert not users.upserted[-1].has_active_access(_NOW)
    assert notifier.user_messages and notifier.user_messages[0][0] == 42
