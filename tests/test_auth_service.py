from __future__ import annotations

from datetime import datetime

import pytest
from app.application.ports.security import InitDataError, TelegramUser
from app.application.services.auth_service import AuthService
from app.domain.entities.enums import UserStatus
from app.domain.entities.user import User


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


async def test_creates_new_user_on_first_auth() -> None:
    repo = _FakeUserRepo()
    service = AuthService(_FakeVerifier(TelegramUser(id=7, username="neo")), repo)

    user = await service.authenticate("valid")

    assert user.telegram_id == 7
    assert user.status is UserStatus.NEW
    assert 7 in repo.store


async def test_returns_existing_user() -> None:
    repo = _FakeUserRepo()
    repo.store[7] = User(telegram_id=7, username="neo", status=UserStatus.ACTIVE)
    service = AuthService(_FakeVerifier(TelegramUser(id=7, username="neo")), repo)

    user = await service.authenticate("valid")

    assert user.status is UserStatus.ACTIVE


async def test_rejects_invalid_init_data() -> None:
    service = AuthService(_FakeVerifier(TelegramUser(id=7)), _FakeUserRepo())

    with pytest.raises(InitDataError):
        await service.authenticate("bad")
