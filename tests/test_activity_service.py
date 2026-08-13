"""Юнит-тесты фиксации /start (без БД).

Ключевой инвариант — НЕ затирать существующего юзера: `upsert` пишет `status`/
`expires_at` из переданного объекта, поэтому «пустой» User для того, кто уже оплатил
подписку, отобрал бы у него доступ. /start жмут и действующие подписчики.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.application.services.activity_service import UserActivityService
from app.domain.analytics.events import EventKind
from app.domain.entities.enums import UserStatus
from app.domain.entities.user import User

from tests.fakes import FakeEvents

_NOW = datetime(2026, 8, 13, tzinfo=UTC)


class _FakeUsers:
    def __init__(self, seed: User | None = None) -> None:
        self.store: dict[int, User] = {seed.telegram_id: seed} if seed else {}
        self.upserts = 0

    async def get(self, telegram_id: int) -> User | None:
        return self.store.get(telegram_id)

    async def upsert(self, user: User) -> User:
        self.upserts += 1
        self.store[user.telegram_id] = user
        return user


async def test_start_creates_new_user_and_records_event() -> None:
    users = _FakeUsers()
    events = FakeEvents()

    await UserActivityService(users, events).register_start(42, "neo")

    created = users.store[42]
    assert created.status is UserStatus.NEW
    assert created.username == "neo"
    assert events.kinds_for(42) == [EventKind.START]


async def test_start_does_not_wipe_active_subscription() -> None:
    active = User(
        telegram_id=42,
        username="neo",
        status=UserStatus.ACTIVE,
        expires_at=_NOW + timedelta(days=10),
        selected_tariff="1_month",
    )
    users = _FakeUsers(active)
    events = FakeEvents()

    await UserActivityService(users, events).register_start(42, "neo")

    assert users.store[42].status is UserStatus.ACTIVE
    assert users.store[42].expires_at == _NOW + timedelta(days=10)
    assert users.upserts == 0  # ничего не изменилось — лишнего UPDATE нет
    assert events.kinds_for(42) == [EventKind.START]


async def test_start_refreshes_changed_username() -> None:
    users = _FakeUsers(User(telegram_id=42, username="old", status=UserStatus.ACTIVE))
    events = FakeEvents()

    await UserActivityService(users, events).register_start(42, "new")

    assert users.store[42].username == "new"
    assert users.store[42].status is UserStatus.ACTIVE  # статус не пострадал
    assert users.upserts == 1
