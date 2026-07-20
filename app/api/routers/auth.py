"""POST /api/auth — авторизация Web App по initData (заголовок Authorization)."""

from __future__ import annotations

from datetime import UTC, datetime

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Header, HTTPException

from app.api.schemas.auth import AuthOut
from app.application.ports.security import InitDataError
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
    # Битый/отсутствующий/просроченный initData — это 401 (клиент не в Telegram или
    # реплей), а НЕ 500: без catch InitDataError всплывал необработанным (Internal Error),
    # и фронт валился в общий экран ошибки вместо понятного «откройте через Telegram».
    try:
        user = await auth.authenticate(authorization)
    except InitDataError as exc:
        raise HTTPException(status_code=401, detail="invalid_init_data") from exc
    token = await sessions.create(user.telegram_id, user.username)
    return AuthOut.from_domain(user, datetime.now(UTC), token=token)
