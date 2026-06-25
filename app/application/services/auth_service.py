"""Авторизация Web App по initData."""

from __future__ import annotations

from app.application.ports.repositories import UserRepository
from app.application.ports.security import InitDataVerifier
from app.domain.entities.user import User


class AuthService:
    def __init__(self, verifier: InitDataVerifier, users: UserRepository) -> None:
        self._verifier = verifier
        self._users = users

    async def authenticate(self, init_data: str) -> User:
        """Проверить initData (HMAC), найти юзера или создать нового со статусом NEW.

        Алгоритм:
          1. tg_user = self._verifier.verify(init_data)  # бросит InitDataError
          2. user = await self._users.get(tg_user.id)
          3. если None — upsert нового User(status=NEW), вернуть.
        """
        raise NotImplementedError
