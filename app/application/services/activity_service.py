"""Фиксация пользователя при контакте с ботом (/start).

До этого юзер появлялся в БД только после открытия Mini App (`AuthService`), поэтому
нажавшие /start и не дошедшие до кинотеатра были невидимы — ни в статистике, ни как
аудитория рассылок. Хендлер бота остаётся тонким: вся логика «завести/обновить» здесь.
"""

from __future__ import annotations

from app.application.ports.repositories import UserEventRepository, UserRepository
from app.domain.analytics.events import EventKind
from app.domain.entities.user import User


class UserActivityService:
    def __init__(self, users: UserRepository, events: UserEventRepository) -> None:
        self._users = users
        self._events = events

    async def register_start(self, telegram_id: int, username: str | None) -> None:
        """Нажал /start: завести юзера (если новый), освежить хэндл, записать событие."""
        user = await self._users.get(telegram_id)
        if user is None:
            # Новый: статус NEW, подписки нет. Только здесь можно слать «пустого» User —
            # для существующего это затёрло бы `status`/`expires_at` (upsert пишет их
            # из переданного объекта) и отобрало бы у человека оплаченную подписку.
            await self._users.upsert(User(telegram_id=telegram_id, username=username))
        elif username is not None and username != user.username:
            # Хэндл мог появиться или смениться — он единственный способ админа ответить
            # на чек/обращение (та же причина, что в `AuthService.authenticate`).
            user.username = username
            await self._users.upsert(user)
        await self._events.add(telegram_id, EventKind.START)
