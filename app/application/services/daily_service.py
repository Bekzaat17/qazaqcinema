"""Фильм дня: какой фильм сегодня открыт всем бесплатно.

Тонкая обвязка над чистым правилом (`domain/catalog/daily`): достать пул id, выбрать
детерминированно по местным суткам, вернуть карточку. Отдельным сервисом, а не методом
каталога, потому что ответ нужен ДВУМ разным сценариям и обязан совпадать: витрине
(hero главной) и выдаче видео (`PlaybackService` пускает без подписки именно этот фильм).
Разъедься эти два места — человек увидел бы «Тегін көру» и получил 403.
"""

from __future__ import annotations

from datetime import datetime

from app.application.ports.repositories import MovieRepository
from app.domain.catalog.daily import pick_daily_id
from app.domain.entities.movie import Movie


class DailyMovieService:
    def __init__(self, movies: MovieRepository) -> None:
        self._movies = movies

    async def today_id(self, now: datetime) -> int | None:
        """id сегодняшнего бесплатного фильма (пустой каталог → None)."""
        return pick_daily_id(await self._movies.list_rotation_ids(), now)

    async def today(self, now: datetime) -> Movie | None:
        movie_id = await self.today_id(now)
        return None if movie_id is None else await self._movies.get(movie_id)
