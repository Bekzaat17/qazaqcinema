"""Порт серверных сессий Web App (DIP).

initData остаётся **bootstrap-ом** (HMAC один раз при входе), далее клиент ходит с
непрозрачным `session_token`. Токен — только идентификатор сессии (данных доступа в нём
нет: статус/срок берутся из БД — источник правды). Реализация —
`infrastructure/cache/session.py` (Redis `session:<uuid>` → JSON, TTL 24 ч).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Session:
    user_id: int
    username: str | None = None


class SessionStore(Protocol):
    async def create(self, user_id: int, username: str | None) -> str | None:
        """Завести сессию, вернуть токен. None — если хранилище недоступно (fail-open:
        клиент останется на initData как на фолбэке)."""
        ...

    async def get(self, token: str) -> Session | None:
        """Сессия по токену. None — токен неизвестен/протух ИЛИ Redis недоступен."""
        ...
