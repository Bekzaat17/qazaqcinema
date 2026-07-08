"""Юнит-тесты движка доступа SubscriptionService на фейках (без БД и aiogram).

Проверяем ядро Фазы 6: activate выдаёт ACTIVE с корректным сроком (новый/продление/
после истечения) и уведомляет юзера; expire_due гасит ТОЛЬКО просроченных и считает их.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.application.services.subscription_service import SubscriptionService
from app.domain.entities.delivery import VideoDelivery
from app.domain.entities.enums import UserStatus
from app.domain.entities.user import User
from app.domain.tariffs.catalog import get_tariff

_NOW = datetime(2026, 6, 29, tzinfo=UTC)
DAY = get_tariff("1_day")
MONTH = get_tariff("1_month")
assert DAY is not None and MONTH is not None  # тарифы из каталога — для типов и сохранности


class _FakeUsers:
    def __init__(self, expired: list[User] | None = None) -> None:
        self._expired = expired or []
        self.upserted: list[User] = []

    async def get(self, telegram_id: int) -> User | None:  # не используется тут
        return None

    async def upsert(self, user: User) -> User:
        self.upserted.append(user)
        return user

    async def list_expired(self, now: datetime) -> list[User]:
        return list(self._expired)


class _FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []
        self.deleted: list[tuple[int, int]] = []

    async def notify_user(self, telegram_id: int, text: str) -> None:
        self.messages.append((telegram_id, text))

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        self.deleted.append((chat_id, message_id))


class _FakeDeliveries:
    """Фейк VideoDeliveryRepository: заранее посеянные выдачи по юзерам."""

    def __init__(self, seed: dict[int, list[VideoDelivery]] | None = None) -> None:
        self._by_user: dict[int, list[VideoDelivery]] = seed or {}
        self.cleared: list[int] = []

    async def add(self, user_id: int, chat_id: int, message_id: int) -> None:
        self._by_user.setdefault(user_id, []).append(VideoDelivery(chat_id, message_id))

    async def list_for_user(self, user_id: int) -> list[VideoDelivery]:
        return list(self._by_user.get(user_id, []))

    async def clear_for_user(self, user_id: int) -> None:
        self.cleared.append(user_id)
        self._by_user.pop(user_id, None)


async def test_activate_grants_access_from_now_for_new_user() -> None:
    users = _FakeUsers()
    notifier = _FakeNotifier()
    service = SubscriptionService(users, notifier, _FakeDeliveries())
    user = User(telegram_id=42, status=UserStatus.NEW)

    result = await service.activate(user, MONTH, _NOW)

    assert result.status is UserStatus.ACTIVE
    assert result.expires_at == _NOW + timedelta(days=30)
    assert result.selected_tariff == "1_month"
    assert result.has_active_access(_NOW) is True
    assert users.upserted == [result]
    assert notifier.messages and notifier.messages[0][0] == 42


async def test_activate_extends_running_subscription() -> None:
    users = _FakeUsers()
    service = SubscriptionService(users, _FakeNotifier(), _FakeDeliveries())
    current = _NOW + timedelta(days=5)
    user = User(telegram_id=1, status=UserStatus.ACTIVE, expires_at=current)

    result = await service.activate(user, DAY, _NOW)

    # продлеваем от текущего срока, а не от now
    assert result.expires_at == current + timedelta(days=1)


async def test_activate_counts_from_now_when_expired() -> None:
    users = _FakeUsers()
    service = SubscriptionService(users, _FakeNotifier(), _FakeDeliveries())
    past = _NOW - timedelta(days=3)
    user = User(telegram_id=1, status=UserStatus.EXPIRED, expires_at=past)

    result = await service.activate(user, DAY, _NOW)

    assert result.expires_at == _NOW + timedelta(days=1)
    assert result.status is UserStatus.ACTIVE


async def test_expire_due_marks_only_expired_and_returns_count() -> None:
    a = User(telegram_id=1, status=UserStatus.ACTIVE, expires_at=_NOW - timedelta(days=1))
    b = User(telegram_id=2, status=UserStatus.ACTIVE, expires_at=_NOW - timedelta(hours=1))
    users = _FakeUsers(expired=[a, b])
    notifier = _FakeNotifier()
    # У юзера 1 — две выданные видео, у юзера 2 — одна: при истечении их надо удалить.
    deliveries = _FakeDeliveries(
        {1: [VideoDelivery(1, 101), VideoDelivery(1, 102)], 2: [VideoDelivery(2, 201)]}
    )
    service = SubscriptionService(users, notifier, deliveries)

    count = await service.expire_due(_NOW)

    assert count == 2
    assert all(u.status is UserStatus.EXPIRED for u in users.upserted)
    assert {u.telegram_id for u in users.upserted} == {1, 2}
    # оба юзера уведомлены об истечении подписки
    assert {tid for tid, _ in notifier.messages} == {1, 2}
    # видео обоих юзеров удалены из чатов и записи о выдачах вычищены
    assert set(notifier.deleted) == {(1, 101), (1, 102), (2, 201)}
    assert set(deliveries.cleared) == {1, 2}


async def test_expire_due_no_expired_users() -> None:
    users = _FakeUsers(expired=[])
    service = SubscriptionService(users, _FakeNotifier(), _FakeDeliveries())

    count = await service.expire_due(_NOW)

    assert count == 0
    assert users.upserted == []
