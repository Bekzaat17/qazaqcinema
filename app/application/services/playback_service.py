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

from app.application.ports.repositories import MovieRepository
from app.application.ports.telegram import TelegramNotifier
from app.domain.entities.user import User


class PlaybackOutcome(Enum):
    DELIVERED = auto()   # видео отправлено в личку (protect_content)
    NO_ACCESS = auto()   # нет активной подписки → фронт показывает пэйволл
    NOT_FOUND = auto()   # фильма с таким id нет


class PlaybackService:
    def __init__(self, movies: MovieRepository, notifier: TelegramNotifier) -> None:
        self._movies = movies
        self._notifier = notifier

    async def deliver(self, user: User, movie_id: int, now: datetime) -> PlaybackOutcome:
        # Доступ проверяем ПЕРВЫМ: без подписки даже не раскрываем, есть ли фильм.
        if not user.has_active_access(now):
            return PlaybackOutcome.NO_ACCESS
        movie = await self._movies.get(movie_id)
        if movie is None:
            return PlaybackOutcome.NOT_FOUND
        await self._notifier.send_protected_video(
            user.telegram_id, movie.telegram_file_id, caption=movie.title_kk
        )
        return PlaybackOutcome.DELIVERED
