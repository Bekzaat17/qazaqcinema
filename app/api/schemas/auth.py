"""DTO результата авторизации Web App."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.domain.entities.user import User


class AuthOut(BaseModel):
    telegram_id: int
    status: str
    expires_at: datetime | None = None
    has_access: bool
    # Сессионный токен (Фаза 11.1): клиент кладёт его в localStorage и шлёт в Authorization
    # вместо initData. None — Redis недоступен, клиент остаётся на initData (fail-open).
    token: str | None = None
    # Начальное состояние тумблера рассылок (Фаза 12) — фронт рисует профиль без доп. запроса.
    notifications_enabled: bool = True
    # Подарочный первый фильм. Фронт по этим двум полям решает, что показать вместо
    # пэйволла: приглашение «первый фильм за наш счёт» (подарок цел) или бейдж «Сыйлық»
    # на уже подаренном фильме. Поля приходят и из `GET /api/me`, который фронт опрашивает,
    # — состояние подарка меняется на сервере и должно доезжать без перезахода.
    free_view_available: bool = True
    free_view_movie_id: int | None = None

    @classmethod
    def from_domain(cls, user: User, now: datetime, token: str | None = None) -> AuthOut:
        return cls(
            telegram_id=user.telegram_id,
            status=user.status.value,
            expires_at=user.expires_at,
            has_access=user.has_active_access(now),
            token=token,
            notifications_enabled=user.notifications_enabled,
            free_view_available=user.can_use_free_view(),
            free_view_movie_id=user.free_view_movie_id,
        )
