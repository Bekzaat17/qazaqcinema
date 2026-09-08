"""Порт валидации Telegram WebApp initData (HMAC по токену бота)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.errors import AppError


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
    # `is_premium` в initData — платит ли человек Telegram сам. Тоже внутри подписанной
    # строки, поэтому полю можно верить. Признак аудитории для отчёта, не право доступа.
    is_premium: bool = False


class InitDataError(AppError, ValueError):
    """initData не прошёл валидацию (подделка/протух/битый)."""


class InitDataVerifier(Protocol):
    def verify(self, init_data: str) -> TelegramUser:
        """Вернуть пользователя при валидном initData, иначе бросить InitDataError."""
        ...
