"""POST /api/auth — авторизация Web App по initData (заголовок Authorization)."""

from __future__ import annotations

from datetime import UTC, datetime

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Header

from app.api.schemas.auth import AuthOut
from app.application.ports.session import SessionStore
from app.application.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"], route_class=DishkaRoute)


@router.post("", response_model=AuthOut)
async def authenticate(
    auth: FromDishka[AuthService],
    sessions: FromDishka[SessionStore],
    authorization: str = Header(..., description="Telegram WebApp initData"),
) -> AuthOut:
    """Bootstrap-вход по initData (HMAC) → заводим серверную сессию, отдаём токен (Фаза 11.1).

    Токен — идентификатор сессии в Redis (TTL 24 ч); клиент дальше шлёт его вместо initData.
    Redis недоступен → `create` вернёт None, клиент останется на initData (fail-open).
    """
    user = await auth.authenticate(authorization)
    token = await sessions.create(user.telegram_id, user.username)
    return AuthOut.from_domain(user, datetime.now(UTC), token=token)
