"""Порт валидации Telegram WebApp initData (HMAC по токену бота)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class TelegramUser:
    id: int
    username: str | None = None
    first_name: str | None = None
    # Разрешил ли человек боту писать ему в личку (`allows_write_to_pm` в initData).
    # Для нас это тот же факт, что и открытый чат: видео уходит сообщением, и Telegram
    # пускает его либо после /start, либо после этого разрешения. Приходит уже в
    # подписанном initData, поэтому доверять полю можно — подделка сломает HMAC.
    allows_write_to_pm: bool = False


class InitDataError(ValueError):
    """initData не прошёл валидацию (подделка/протух/битый)."""


class InitDataVerifier(Protocol):
    def verify(self, init_data: str) -> TelegramUser:
        """Вернуть пользователя при валидном initData, иначе бросить InitDataError."""
        ...
