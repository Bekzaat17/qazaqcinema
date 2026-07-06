"""Use-case «отдать видео подписчику» с защитой контента.

Гейт доступа — единый источник правды `User.has_active_access`. Видео НИКОГДА не
уходит без активной подписки. Отправка — через порт `TelegramNotifier`
(`send_protected_video` → `bot.send_video(protect_content=True)`), `telegram_file_id`
наружу (в API-DTO) не отдаётся — его видит только бот.

Почему не inline: `InlineQueryResult*` не поддерживают `protect_content` (проверено на
aiogram 3.x), поэтому защищённую выдачу делает бот напрямую в личку, а триггерит её
API-эндпоинт `/play` (initData-гейт) или, в будущем, deep-link.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum, auto

from app.application.ports.lock import Lock
from app.application.ports.repositories import MovieRepository
from app.application.ports.telegram import RecipientUnreachableError, TelegramNotifier
from app.domain.entities.user import User


class PlaybackOutcome(Enum):
    DELIVERED = auto()    # видео отправлено в личку (protect_content)
    NO_ACCESS = auto()    # нет активной подписки → фронт показывает пэйволл
    NOT_FOUND = auto()    # фильма с таким id нет
    BOT_BLOCKED = auto()  # получатель не открыл чат с ботом → фронт просит открыть бота


class PlaybackService:
    # TTL лока отправки: столько секунд повторные /play той же пары юзер+фильм — no-op.
    _SEND_LOCK_TTL = 3

    def __init__(self, movies: MovieRepository, notifier: TelegramNotifier, lock: Lock) -> None:
        self._movies = movies
        self._notifier = notifier
        self._lock = lock

    async def deliver(self, user: User, movie_id: int, now: datetime) -> PlaybackOutcome:
        # Доступ проверяем ПЕРВЫМ: без подписки даже не раскрываем, есть ли фильм.
        if not user.has_active_access(now):
            return PlaybackOutcome.NO_ACCESS
        movie = await self._movies.get(movie_id)
        if movie is None:
            return PlaybackOutcome.NOT_FOUND
        # Анти-двойной-клик: на плохом инете юзер жмёт «Көру» много раз. Лок на
        # несколько секунд → одна отправка; повтор в окне — тихий no-op, но всё равно
        # DELIVERED, чтобы фронт показал ту же модалку «видео отправлено», а не ошибку.
        lock_key = f"send_video:{user.telegram_id}:{movie_id}"
        if not await self._lock.acquire(lock_key, self._SEND_LOCK_TTL):
            return PlaybackOutcome.DELIVERED
        try:
            await self._notifier.send_protected_video(
                user.telegram_id, movie.telegram_file_id, caption=movie.title_kk
            )
        except RecipientUnreachableError:
            # Юзер открыл Mini App, но не начал чат с ботом. Лок (TTL ~3 c) не снимаем:
            # окно мало, а доступ к боту юзер чинит дольше → ложного «доставлено» не будет.
            return PlaybackOutcome.BOT_BLOCKED
        # Считаем просмотр только на реальной доставке (Фаза 13): повтор-в-окне не дошёл
        # сюда (лок вернул DELIVERED раньше) → двойной клик не накручивает счётчик.
        await self._movies.increment_play_count(movie_id)
        return PlaybackOutcome.DELIVERED
