"""Сущность «Пользователь» с доменной логикой проверки доступа."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.entities.enums import UserStatus


@dataclass(slots=True)
class User:
    telegram_id: int
    username: str | None = None
    status: UserStatus = UserStatus.NEW
    expires_at: datetime | None = None
    selected_tariff: str | None = None
    notifications_enabled: bool = True  # рассылки о новинках; opt-out, по умолчанию ВКЛ (Фаза 12)

    def has_active_access(self, now: datetime) -> bool:
        """Единственный источник правды о доступе (used: inline-выдача, API-гейт)."""
        return (
            self.status is UserStatus.ACTIVE
            and self.expires_at is not None
            and self.expires_at > now
        )
