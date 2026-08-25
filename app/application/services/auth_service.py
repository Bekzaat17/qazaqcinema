"""Авторизация Web App по initData."""

from __future__ import annotations

from datetime import UTC, datetime

from app.application.ports.repositories import UserEventRepository, UserRepository
from app.application.ports.security import InitDataVerifier, TelegramUser
from app.application.services.activity_service import UserActivityService
from app.domain.analytics.events import EventKind
from app.domain.entities.enums import UserStatus
from app.domain.entities.user import User


class AuthService:
    def __init__(
        self,
        verifier: InitDataVerifier,
        users: UserRepository,
        events: UserEventRepository,
        activity: UserActivityService,
    ) -> None:
        self._verifier = verifier
        self._users = users
        self._events = events
        self._activity = activity

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
            user = await self._users.upsert(
                User(
                    telegram_id=tg_user.id,
                    username=tg_user.username,
                    status=UserStatus.NEW,
                )
            )
            return await self._sync_write_access(user, tg_user)
        # Хэндл мог появиться или смениться после первого входа, а он — единственный
        # способ админа ответить на чек/обращение (см. domain/mention.py). Пишем только
        # при расхождении: логин частый, лишний UPDATE ни к чему.
        if tg_user.username is not None and tg_user.username != user.username:
            user.username = tg_user.username
            await self._users.upsert(user)
        return await self._sync_write_access(user, tg_user)

    async def _sync_write_access(self, user: User, tg_user: TelegramUser) -> User:
        """Признать открытым чат, если Telegram сам сообщил о разрешении писать в личку.

        `allows_write_to_pm` приходит в подписанном initData — то есть ровно при открытии
        Mini App, без единого действия человека. Для тех, кто разрешение уже давал (нажимал
        START, соглашался в попапе, просто писал боту раньше), кинотеатр открывается сам:
        шторки «Ботты іске қосыңыз» они больше не видят.

        Проверка идёт при КАЖДОМ входе, но UPDATE случается один раз — пока факт не
        зафиксирован. Обратное (Telegram молчит → снять признак) НЕ делаем: поле есть не
        во всех версиях клиента, и его отсутствие значит «не знаю», а не «доступа нет».
        Снимает признак только реальная недоставка в `PlaybackService`.
        """
        if not tg_user.allows_write_to_pm or user.has_bot_chat():
            return user
        now = datetime.now(UTC)
        await self._activity.register_write_access(user.telegram_id, now, source="auto")
        user.bot_started_at = now
        return user
