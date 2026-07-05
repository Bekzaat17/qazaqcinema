"""Юнит-тест двухрежимной `get_current_user` (Фаза 11.1).

Authorization с `=` → initData (stateless AuthService, фолбэк без Redis); без `=` →
session-токен (Redis → User из БД). Порты — фейки; проверяем маршрутизацию по форме
токена и коды 401. Реальный Request нужен лишь ради `request.state.dishka_container`.
"""

from __future__ import annotations

import pytest
from app.api.deps.auth import get_current_user
from app.application.ports.repositories import UserRepository
from app.application.ports.security import InitDataError
from app.application.ports.session import Session, SessionStore
from app.application.services.auth_service import AuthService
from app.domain.entities.enums import UserStatus
from app.domain.entities.user import User
from fastapi import HTTPException
from starlette.requests import Request

_TOKEN = "deadbeef" * 4  # 32 hex-символа, без '=' → трактуется как session-токен


def _user(uid: int = 42) -> User:
    return User(telegram_id=uid, status=UserStatus.ACTIVE)


class _FakeAuthService:
    def __init__(self, user: User | None) -> None:
        self._user = user
        self.calls: list[str] = []

    async def authenticate(self, init_data: str) -> User:
        self.calls.append(init_data)
        if self._user is None:
            raise InitDataError("bad initData")
        return self._user


class _FakeSessions:
    def __init__(self, session: Session | None) -> None:
        self._session = session

    async def get(self, token: str) -> Session | None:
        return self._session


class _FakeUsers:
    def __init__(self, user: User | None) -> None:
        self._user = user

    async def get(self, telegram_id: int) -> User | None:
        return self._user


class _FakeContainer:
    def __init__(self, mapping: dict[type, object]) -> None:
        self._mapping = mapping

    async def get(self, tp: type) -> object:
        return self._mapping[tp]


def _request(mapping: dict[type, object]) -> Request:
    request = Request({"type": "http", "headers": [], "state": {}})
    request.state.dishka_container = _FakeContainer(mapping)
    return request


async def test_init_data_path_validates_via_auth_service() -> None:
    user = _user()
    auth = _FakeAuthService(user)
    request = _request({AuthService: auth})

    result = await get_current_user(request, "user=%7B%7D&auth_date=1&hash=abc")

    assert result is user
    assert auth.calls == ["user=%7B%7D&auth_date=1&hash=abc"]  # ушло в initData-путь


async def test_invalid_init_data_returns_401() -> None:
    request = _request({AuthService: _FakeAuthService(None)})

    with pytest.raises(HTTPException) as exc:
        await get_current_user(request, "auth_date=1&hash=bad")

    assert exc.value.status_code == 401
    assert exc.value.detail == "invalid_init_data"


async def test_session_token_path_loads_user_from_db() -> None:
    user = _user(7)
    request = _request(
        {
            SessionStore: _FakeSessions(Session(user_id=7, username="x")),
            UserRepository: _FakeUsers(user),
        }
    )

    result = await get_current_user(request, _TOKEN)

    assert result is user


async def test_expired_session_returns_401() -> None:
    request = _request({SessionStore: _FakeSessions(None)})

    with pytest.raises(HTTPException) as exc:
        await get_current_user(request, _TOKEN)

    assert exc.value.status_code == 401
    assert exc.value.detail == "session_expired"
