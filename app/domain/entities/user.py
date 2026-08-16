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
    # Подарочный первый фильм: человек должен увидеть продукт ДО пэйволла. Оба поля
    # проставляются один раз, атомарно (`UserRepository.claim_free_view`).
    free_view_used_at: datetime | None = None  # None → подарок ещё не потрачен
    free_view_movie_id: int | None = None      # какой фильм подарен (None у плативших-до-запуска)

    def has_active_access(self, now: datetime) -> bool:
        """Единственный источник правды о доступе (used: inline-выдача, API-гейт)."""
        return (
            self.status is UserStatus.ACTIVE
            and self.expires_at is not None
            and self.expires_at > now
        )

    def can_use_free_view(self) -> bool:
        """Подарок ещё не потрачен → человек вправе открыть ОДИН любой фильм бесплатно."""
        return self.free_view_used_at is None

    def is_gifted_movie(self, movie_id: int) -> bool:
        """Этот фильм ему уже подарен → повторная выдача бесплатна и после чистки видео.

        Telegram-сообщение с видео мы сносим через ~40 ч (`VideoRetentionService`), и без
        этого правила человек терял бы подарок из-за нашей же уборки — выглядело бы как
        «дали и отняли». Бесплатен только ЭТОТ фильм: любой другой упирается в пэйволл.
        """
        return self.free_view_movie_id == movie_id
