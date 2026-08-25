from __future__ import annotations

from datetime import datetime

import pytest
from app.application.ports.security import InitDataError, TelegramUser
from app.application.services.activity_service import UserActivityService
from app.application.services.auth_service import AuthService
from app.domain.analytics.events import EventKind
from app.domain.entities.enums import UserStatus
from app.domain.entities.user import User

from tests.fakes import FakeEvents


class _FakeVerifier:
    def __init__(self, user: TelegramUser) -> None:
        self._user = user

    def verify(self, init_data: str) -> TelegramUser:
        if init_data == "bad":
            raise InitDataError("подпись не совпала")
        return self._user


class _FakeUserRepo:
    def __init__(self) -> None:
        self.store: dict[int, User] = {}

    async def get(self, telegram_id: int) -> User | None:
        return self.store.get(telegram_id)

    async def upsert(self, user: User) -> User:
        self.store[user.telegram_id] = user
        return user

    async def list_expired(self, now: datetime) -> list[User]:
        return []

    async def set_bot_started(self, telegram_id: int, at: datetime | None) -> None:
        if (user := self.store.get(telegram_id)) is not None:
            user.bot_started_at = at


def _service(
    tg_user: TelegramUser, repo: _FakeUserRepo, events: FakeEvents | None = None
) -> AuthService:
    """Сборка сервиса: журнал и `UserActivityService` нужны всем тестам одинаково."""
    log = events or FakeEvents()
    return AuthService(_FakeVerifier(tg_user), repo, log, UserActivityService(repo, log))


async def test_creates_new_user_on_first_auth() -> None:
    repo = _FakeUserRepo()
    service = _service(TelegramUser(id=7, username="neo"), repo)

    user = await service.authenticate("valid")

    assert user.telegram_id == 7
    assert user.status is UserStatus.NEW
    assert 7 in repo.store


async def test_returns_existing_user() -> None:
    repo = _FakeUserRepo()
    repo.store[7] = User(telegram_id=7, username="neo", status=UserStatus.ACTIVE)
    service = _service(TelegramUser(id=7, username="neo"), repo)

    user = await service.authenticate("valid")

    assert user.status is UserStatus.ACTIVE


async def test_refreshes_username_when_it_changed() -> None:
    """Хэндл мог появиться/смениться после первого входа — админам нужен свежий."""
    repo = _FakeUserRepo()
    repo.store[7] = User(telegram_id=7, username=None, status=UserStatus.ACTIVE)
    service = _service(TelegramUser(id=7, username="neo"), repo)

    user = await service.authenticate("valid")

    assert user.username == "neo"
    assert repo.store[7].username == "neo"
    assert user.status is UserStatus.ACTIVE  # прочие поля не тронуты


async def test_keeps_stored_username_when_telegram_sends_none() -> None:
    """initData без username (юзер скрыл хэндл) не должен затирать известный нам."""
    repo = _FakeUserRepo()
    repo.store[7] = User(telegram_id=7, username="neo", status=UserStatus.ACTIVE)
    service = _service(TelegramUser(id=7), repo)

    user = await service.authenticate("valid")

    assert user.username == "neo"


async def test_rejects_invalid_init_data() -> None:
    service = _service(TelegramUser(id=7), _FakeUserRepo())

    with pytest.raises(InitDataError):
        await service.authenticate("bad")


async def test_write_access_from_init_data_opens_cinema_silently() -> None:
    """Telegram сам сказал, что боту писать можно, — кинотеатр открыт без единого клика."""
    repo = _FakeUserRepo()
    repo.store[7] = User(telegram_id=7, username="neo", status=UserStatus.NEW)
    events = FakeEvents()
    service = _service(TelegramUser(id=7, username="neo", allows_write_to_pm=True), repo, events)

    user = await service.authenticate("valid")

    assert user.has_bot_chat()  # AuthOut.bot_started → фронт не покажет шторку
    assert repo.store[7].bot_started_at is not None
    assert events.added == [(7, EventKind.WRITE_ACCESS, "auto")]


async def test_write_access_recorded_once() -> None:
    """Проверка идёт на каждом входе, а UPDATE и событие — только пока факта нет."""
    repo = _FakeUserRepo()
    repo.store[7] = User(telegram_id=7, status=UserStatus.NEW)
    events = FakeEvents()
    service = _service(TelegramUser(id=7, allows_write_to_pm=True), repo, events)

    await service.authenticate("valid")
    await service.authenticate("valid")

    assert events.kinds_for(7) == [EventKind.WRITE_ACCESS]


async def test_new_user_with_write_access_gets_it_after_creation() -> None:
    """Первый вход по ссылке: строки ещё нет, признак ставится сразу после неё."""
    repo = _FakeUserRepo()
    service = _service(TelegramUser(id=7, allows_write_to_pm=True), repo)

    user = await service.authenticate("valid")

    assert user.has_bot_chat()
    assert repo.store[7].bot_started_at is not None


async def test_silence_about_write_access_does_not_revoke_it() -> None:
    """Поле есть не во всех клиентах: его отсутствие — «не знаю», а не «доступа нет»."""
    repo = _FakeUserRepo()
    known = User(telegram_id=7, status=UserStatus.ACTIVE)
    known.bot_started_at = datetime(2026, 8, 20)
    repo.store[7] = known
    events = FakeEvents()
    service = _service(TelegramUser(id=7), repo, events)

    user = await service.authenticate("valid")

    assert user.bot_started_at == datetime(2026, 8, 20)
    assert events.added == []
