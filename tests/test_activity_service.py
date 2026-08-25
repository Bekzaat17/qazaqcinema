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
        self.bot_started: list[tuple[int, datetime | None]] = []

    async def get(self, telegram_id: int) -> User | None:
        return self.store.get(telegram_id)

    async def upsert(self, user: User) -> User:
        self.upserts += 1
        self.store[user.telegram_id] = user
        return user

    async def set_bot_started(self, telegram_id: int, at: datetime | None) -> None:
        self.bot_started.append((telegram_id, at))
        if (user := self.store.get(telegram_id)) is not None:
            user.bot_started_at = at


async def test_start_creates_new_user_and_records_event() -> None:
    users = _FakeUsers()
    events = FakeEvents()

    await UserActivityService(users, events).register_start(42, "neo", _NOW)

    created = users.store[42]
    assert created.status is UserStatus.NEW
    assert created.username == "neo"
    assert created.bot_started_at == _NOW  # чат с ботом открыт → «Көру» дойдёт до лички
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

    await UserActivityService(users, events).register_start(42, "neo", _NOW)

    assert users.store[42].status is UserStatus.ACTIVE
    assert users.store[42].expires_at == _NOW + timedelta(days=10)
    assert users.upserts == 0  # ничего не изменилось — лишнего UPDATE нет
    assert events.kinds_for(42) == [EventKind.START]


async def test_start_refreshes_changed_username() -> None:
    users = _FakeUsers(User(telegram_id=42, username="old", status=UserStatus.ACTIVE))
    events = FakeEvents()

    await UserActivityService(users, events).register_start(42, "new", _NOW)

    assert users.store[42].username == "new"
    assert users.store[42].status is UserStatus.ACTIVE  # статус не пострадал
    assert users.upserts == 1


async def test_write_access_opens_cinema_without_visiting_chat() -> None:
    """Разрешение писать в личку = тот же итог, что и /start, но без ухода в чат."""
    users = _FakeUsers(User(telegram_id=42, username="neo", status=UserStatus.NEW))
    events = FakeEvents()

    await UserActivityService(users, events).register_write_access(42, _NOW, source="prompt")

    assert users.store[42].bot_started_at == _NOW
    assert events.added == [(42, EventKind.WRITE_ACCESS, "prompt")]


async def test_write_access_keeps_source_apart() -> None:
    """«auto» (узнали из initData) и «prompt» (нажал в попапе) — разные дороги воронки."""
    users = _FakeUsers(User(telegram_id=42, status=UserStatus.NEW))
    events = FakeEvents()

    await UserActivityService(users, events).register_write_access(42, _NOW, source="auto")

    assert events.added == [(42, EventKind.WRITE_ACCESS, "auto")]


async def test_paywall_event_carries_movie() -> None:
    users = _FakeUsers()
    events = FakeEvents()

    await UserActivityService(users, events).register_paywall(42, 144)

    assert events.added == [(42, EventKind.PAYWALL, "144")]


async def test_paywall_event_without_movie() -> None:
    """Пэйволл открыт не с карточки (кнопка в профиле) — привязывать не к чему."""
    users = _FakeUsers()
    events = FakeEvents()

    await UserActivityService(users, events).register_paywall(42, None)

    assert events.added == [(42, EventKind.PAYWALL, None)]
