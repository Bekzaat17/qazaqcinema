"""Роутер POST /api/auth: битый initData → 401, а не 500 (регресс-страж).

Раньше `AuthService.authenticate` бросал `InitDataError` необработанным → FastAPI отдавал
500, и фронт валился в общий экран ошибки. Теперь роутер ловит его и возвращает 401
(`invalid_init_data`) — клиент понимает «не в Telegram / реплей», а не «сервер упал».
"""

from __future__ import annotations

import pytest
from app.api.routers.auth import authenticate
from app.application.ports.security import InitDataError
from app.domain.entities.enums import UserStatus
from app.domain.entities.user import User
from fastapi import HTTPException


class _RaisingAuth:
    async def authenticate(self, init_data: str) -> User:
        raise InitDataError("нет поля hash")


class _OkAuth:
    async def authenticate(self, init_data: str) -> User:
        return User(telegram_id=42, status=UserStatus.ACTIVE)


class _FakeSessions:
    async def create(self, telegram_id: int, username: str | None) -> str | None:
        return "tok"


async def test_auth_router_maps_bad_init_data_to_401() -> None:
    with pytest.raises(HTTPException) as exc:
        await authenticate(_RaisingAuth(), _FakeSessions(), "user=x&auth_date=1")
    assert exc.value.status_code == 401
    assert exc.value.detail == "invalid_init_data"


async def test_auth_router_ok_returns_auth_out() -> None:
    out = await authenticate(_OkAuth(), _FakeSessions(), "user=%7B%7D&auth_date=1&hash=a")
    assert out.telegram_id == 42
    assert out.token == "tok"
