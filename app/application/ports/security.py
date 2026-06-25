"""Порт валидации Telegram WebApp initData (HMAC по токену бота)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class TelegramUser:
    id: int
    username: str | None = None
    first_name: str | None = None


class InitDataError(ValueError):
    """initData не прошёл валидацию (подделка/протух/битый)."""


class InitDataVerifier(Protocol):
    def verify(self, init_data: str) -> TelegramUser:
        """Вернуть пользователя при валидном initData, иначе бросить InitDataError."""
        ...
