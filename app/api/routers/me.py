"""Текущий пользователь Web App: свежий статус доступа (опрос) и настройки (Фаза 12)."""

from __future__ import annotations

from datetime import UTC, datetime

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit
from app.api.schemas.auth import AuthOut
from app.application.services.broadcast_service import BroadcastService
from app.domain.entities.user import User

# Rate-limit (данные): тумблер — write-ручка; скромный лимит на IP, консистентно с прочими
# мутирующими эндпоинтами (payments). До auth-ключа хватает IP (см. api/deps/rate_limit.py).
_write_rate_limited = Depends(rate_limit(limit=30, window_seconds=60, scope="me"))
# Чтение статуса — отдельный, ЩЕДРЫЙ лимит: фронт опрашивает эту ручку, пока чек «на
# проверке», а мобильные юзеры сидят за общим CGNAT-IP (ключ лимитера — IP). Со скромными
# 30/мин десяток человек с одной вышки упёрлись бы в 429 на ровном месте.
_read_rate_limited = Depends(rate_limit(limit=120, window_seconds=60, scope="me_read"))

router = APIRouter(prefix="/api/me", tags=["me"], route_class=DishkaRoute)


class NotificationsIn(BaseModel):
    enabled: bool


class NotificationsOut(BaseModel):
    notifications_enabled: bool


@router.get("", response_model=AuthOut, dependencies=[_read_rate_limited])
async def current_user(user: User = Depends(get_current_user)) -> AuthOut:
    """Свежий статус доступа текущего юзера — БЕЗ создания новой сессии.

    Нужна фронту, чтобы узнавать решение модератора по чеку (✅/❌) не переоткрывая
    Mini App: статус меняет админ извне, и опрашивать ради этого `POST /api/auth`
    нельзя — тот на каждый вызов заводит в Redis новую сессию (мусор с TTL 24 ч).
    Токен здесь не возвращаем: он у клиента уже есть.
    """
    return AuthOut.from_domain(user, datetime.now(UTC))


@router.patch("/notifications", response_model=NotificationsOut, dependencies=[_write_rate_limited])
async def set_notifications(
    body: NotificationsIn,
    broadcast: FromDishka[BroadcastService],
    user: User = Depends(get_current_user),
) -> NotificationsOut:
    """Включить/выключить рассылки о новинках для текущего юзера (тумблер в профиле)."""
    await broadcast.set_user_notifications(user.telegram_id, body.enabled)
    return NotificationsOut(notifications_enabled=body.enabled)
