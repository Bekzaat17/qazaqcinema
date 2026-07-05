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

    @classmethod
    def from_domain(cls, user: User, now: datetime, token: str | None = None) -> AuthOut:
        return cls(
            telegram_id=user.telegram_id,
            status=user.status.value,
            expires_at=user.expires_at,
            has_access=user.has_active_access(now),
            token=token,
        )
