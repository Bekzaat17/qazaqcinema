"""Автонаполнение каталога из постов канала-архива."""

from __future__ import annotations

from app.application.ports.repositories import MovieRepository
from app.application.ports.telegram import TelegramNotifier
from app.domain.entities.movie import Movie
from app.domain.parsing.parsed_movie import ParsedMovie


class MovieIngestionService:
    def __init__(self, movies: MovieRepository, notifier: TelegramNotifier) -> None:
        self._movies = movies
        self._notifier = notifier

    async def ingest(self, parsed: ParsedMovie, telegram_file_id: str) -> Movie:
        """Сохранить распарсенный фильм + DM админам: 'Фильм X добавлен, ID: N'.

        Алгоритм:
          1. movie = Movie(**parsed, telegram_file_id=telegram_file_id)
          2. saved = await self._movies.add(movie)
          3. await self._notifier.notify_admins(f"Фильм «{saved.title}» добавлен. ID: {saved.id}")
          4. вернуть saved.
        """
        raise NotImplementedError
