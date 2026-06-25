"""POST /api/auth — авторизация Web App по initData (заголовок Authorization)."""

from __future__ import annotations

from datetime import UTC, datetime

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Header

from app.api.schemas.auth import AuthOut
from app.application.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"], route_class=DishkaRoute)


@router.post("", response_model=AuthOut)
async def authenticate(
    auth: FromDishka[AuthService],
    authorization: str = Header(..., description="Telegram WebApp initData"),
) -> AuthOut:
    user = await auth.authenticate(authorization)
    return AuthOut.from_domain(user, datetime.now(UTC))
