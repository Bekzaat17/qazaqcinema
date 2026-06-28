"""Авторизация Web App по initData."""

from __future__ import annotations

from app.application.ports.repositories import UserRepository
from app.application.ports.security import InitDataVerifier
from app.domain.entities.enums import UserStatus
from app.domain.entities.user import User


class AuthService:
    def __init__(self, verifier: InitDataVerifier, users: UserRepository) -> None:
        self._verifier = verifier
        self._users = users

    async def authenticate(self, init_data: str) -> User:
        """Проверить initData (HMAC) и вернуть пользователя.

        Первый вход — создаём User со статусом NEW. Бросает InitDataError,
        если подпись initData невалидна.
        """
        tg_user = self._verifier.verify(init_data)
        user = await self._users.get(tg_user.id)
        if user is None:
            user = await self._users.upsert(
                User(
                    telegram_id=tg_user.id,
                    username=tg_user.username,
                    status=UserStatus.NEW,
                )
            )
        return user
