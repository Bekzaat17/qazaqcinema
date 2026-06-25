"""Каталог фильмов для Web App. telegram_file_id наружу не отдаётся (см. API-схемы)."""

from __future__ import annotations

from app.application.ports.repositories import MovieRepository
from app.domain.entities.movie import Movie


class CatalogService:
    def __init__(self, movies: MovieRepository) -> None:
        self._movies = movies

    async def list_movies(self, category: str | None = None) -> list[Movie]:
        raise NotImplementedError

    async def search_movies(self, query: str) -> list[Movie]:
        raise NotImplementedError

    async def get_movie(self, movie_id: int) -> Movie | None:
        raise NotImplementedError
