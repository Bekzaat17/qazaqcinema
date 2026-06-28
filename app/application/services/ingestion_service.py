"""Добавление фильма в каталог. Источник — бот-визард `/add` (FSM).

Сервис чист: знает только порты (репозиторий, хранилище постеров, нотификатор),
ничего про aiogram. Видео уже лежит в канале-архиве (его file_id приходит готовым),
постер приходит байтами и уходит в `PosterStorage` (статика на VPS).
"""

from __future__ import annotations

from app.application.ports.repositories import MovieRepository
from app.application.ports.storage import PosterStorage
from app.application.ports.telegram import TelegramNotifier
from app.domain.entities.movie import Movie


class MovieIngestionService:
    def __init__(
        self,
        movies: MovieRepository,
        notifier: TelegramNotifier,
        posters: PosterStorage,
    ) -> None:
        self._movies = movies
        self._notifier = notifier
        self._posters = posters

    async def ingest(
        self,
        *,
        title_kk: str,
        title_ru: str | None,
        title_original: str | None,
        category: str,
        description: str,
        year: int | None,
        rating: float | None,
        video_file_id: str,
        poster_bytes: bytes,
    ) -> Movie:
        """Сохранить постер, записать фильм в БД, уведомить админов; вернуть сохранённый.

        `video_file_id` — file_id видео в канале-архиве (отдаётся ТОЛЬКО боту).
        `poster_bytes` — скачанный постер; уходит в `PosterStorage` → публичный URL.
        """
        poster_url = await self._posters.save(poster_bytes)
        movie = Movie(
            title_kk=title_kk,
            title_ru=title_ru,
            title_original=title_original,
            category=category,
            description=description,
            poster_url=poster_url,
            telegram_file_id=video_file_id,
            year=year,
            rating=rating,
        )
        saved = await self._movies.add(movie)
        await self._notifier.notify_admins(
            f"✅ Фильм «{saved.title_kk}» добавлен. ID: {saved.id}"
        )
        return saved
