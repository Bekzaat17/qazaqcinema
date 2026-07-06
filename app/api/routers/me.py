"""Настройки текущего пользователя Web App (Фаза 12)."""

from __future__ import annotations

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit
from app.application.services.broadcast_service import BroadcastService
from app.domain.entities.user import User

# Rate-limit (данные): тумблер — write-ручка; скромный лимит на IP, консистентно с прочими
# мутирующими эндпоинтами (payments). До auth-ключа хватает IP (см. api/deps/rate_limit.py).
_rate_limited = Depends(rate_limit(limit=30, window_seconds=60, scope="me"))

router = APIRouter(
    prefix="/api/me", tags=["me"], route_class=DishkaRoute, dependencies=[_rate_limited]
)


class NotificationsIn(BaseModel):
    enabled: bool


class NotificationsOut(BaseModel):
    notifications_enabled: bool


@router.patch("/notifications", response_model=NotificationsOut)
async def set_notifications(
    body: NotificationsIn,
    broadcast: FromDishka[BroadcastService],
    user: User = Depends(get_current_user),
) -> NotificationsOut:
    """Включить/выключить рассылки о новинках для текущего юзера (тумблер в профиле)."""
    await broadcast.set_user_notifications(user.telegram_id, body.enabled)
    return NotificationsOut(notifications_enabled=body.enabled)
