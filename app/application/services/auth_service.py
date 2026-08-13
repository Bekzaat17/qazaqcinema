"""Авторизация Web App по initData."""

from __future__ import annotations

from app.application.ports.repositories import UserEventRepository, UserRepository
from app.application.ports.security import InitDataVerifier
from app.domain.analytics.events import EventKind
from app.domain.entities.enums import UserStatus
from app.domain.entities.user import User


class AuthService:
    def __init__(
        self, verifier: InitDataVerifier, users: UserRepository, events: UserEventRepository
    ) -> None:
        self._verifier = verifier
        self._users = users
        self._events = events

    async def bootstrap(self, init_data: str) -> User:
        """Вход через `POST /api/auth` — то же, что `authenticate`, плюс событие «открыл».

        Событие пишем ИМЕННО здесь, а не в `authenticate`: ту дёргает ещё и
        `get_current_user` на initData-фолбэке, то есть на КАЖДОМ запросе, когда клиент
        остался без сессионного токена (Redis лёг). Считали бы открытия там — метрика
        превратилась бы в счётчик HTTP-запросов.

        Фронт зовёт `/api/auth` на запуске Mini App и ещё раз при 401 (протухшая сессия,
        TTL 24 ч), так что «открытий» может быть чуть больше, чем реальных заходов.
        Поэтому главная цифра отчёта — уникальные ЛЮДИ: на них ре-авторизация не влияет.
        """
        user = await self.authenticate(init_data)
        await self._events.add(user.telegram_id, EventKind.OPEN)
        return user

    async def authenticate(self, init_data: str) -> User:
        """Проверить initData (HMAC) и вернуть пользователя.

        Первый вход — создаём User со статусом NEW. Бросает InitDataError,
        если подпись initData невалидна.
        """
        tg_user = self._verifier.verify(init_data)
        user = await self._users.get(tg_user.id)
        if user is None:
            return await self._users.upsert(
                User(
                    telegram_id=tg_user.id,
                    username=tg_user.username,
                    status=UserStatus.NEW,
                )
            )
        # Хэндл мог появиться или смениться после первого входа, а он — единственный
        # способ админа ответить на чек/обращение (см. domain/mention.py). Пишем только
        # при расхождении: логин частый, лишний UPDATE ни к чему.
        if tg_user.username is not None and tg_user.username != user.username:
            user.username = tg_user.username
            await self._users.upsert(user)
        return user
