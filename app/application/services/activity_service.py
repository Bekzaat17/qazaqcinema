"""Фиксация пользователя при контакте с ботом (/start).

До этого юзер появлялся в БД только после открытия Mini App (`AuthService`), поэтому
нажавшие /start и не дошедшие до кинотеатра были невидимы — ни в статистике, ни как
аудитория рассылок. Хендлер бота остаётся тонким: вся логика «завести/обновить» здесь.
"""

from __future__ import annotations

from datetime import datetime

from app.application.ports.repositories import UserEventRepository, UserRepository
from app.domain.analytics.events import EventKind
from app.domain.entities.user import User


class UserActivityService:
    def __init__(self, users: UserRepository, events: UserEventRepository) -> None:
        self._users = users
        self._events = events

    async def register_start(
        self, telegram_id: int, username: str | None, now: datetime
    ) -> None:
        """Нажал /start: завести юзера (если новый), освежить хэндл, записать событие.

        Здесь же фиксируем главный технический факт — чат с ботом открыт. Telegram не даёт
        боту написать первым, поэтому до /start кинотеатр для человека витрина без выдачи:
        видео уходит только в личку. Mini App читает этот факт и зовёт в бота ЗАРАНЕЕ,
        а не показывает ошибку после того, как подарок уже потрачен.
        """
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
        # Отдельным точечным UPDATE, а не через upsert: факт внешний по отношению к
        # карточке юзера (см. `UserRepository.set_bot_started`), и для НОВОГО юзера он
        # обязан идти после upsert — строки до неё ещё нет.
        await self._users.set_bot_started(telegram_id, now)
        await self._events.add(telegram_id, EventKind.START)

    async def register_write_access(
        self, telegram_id: int, now: datetime, source: str
    ) -> None:
        """Боту разрешили писать в личку — тот же итог, что и /start, но без ухода в чат.

        Telegram даёт два пути к праву написать первым: кнопка START в чате и нативный
        попап `requestWriteAccess()` внутри Mini App. Второй короче на целый экран, и
        именно им теперь открывается кинотеатр для пришедших из поиска — раньше каждый
        третий останавливался здесь и не получал ни одного фильма.

        `source`: "auto" — разрешение уже было, узнали из initData при входе;
        "prompt" — человек только что нажал «Разрешить» в попапе.
        """
        await self._users.set_bot_started(telegram_id, now)
        await self._events.add(telegram_id, EventKind.WRITE_ACCESS, meta=source)

    async def register_paywall(self, telegram_id: int, movie_id: int | None) -> None:
        """Человек упёрся в пэйволл: смотреть хочет, а доступа и подарка уже нет.

        Ключевая точка отказа воронки. Событие есть и в `PlaybackService`, но туда
        попадают лишь те, у кого доступ протух между открытием карточки и нажатием
        «Көру» — единицы. Обычный путь короче: фронт знает про отсутствие доступа сам
        и рисует пэйволл, не спрашивая сервер. Поэтому счётчик и стоял на нуле всё
        время, пока метрика считалась собранной.
        """
        await self._events.add(
            telegram_id, EventKind.PAYWALL, meta=str(movie_id) if movie_id else None
        )
