"""DTO фильма для фронтенда. telegram_file_id НЕ отдаётся наружу (security)."""

from __future__ import annotations

from pydantic import BaseModel

from app.domain.entities.movie import Movie


class MovieOut(BaseModel):
    id: int
    title: str
    description: str
    category: str
    poster_url: str
    year: int | None = None
    rating: float | None = None
    # telegram_file_id ОТСУТСТВУЕТ намеренно — его видит только бот.

    @classmethod
    def from_domain(cls, movie: Movie) -> MovieOut:
        if movie.id is None:
            raise ValueError("movie без id не может быть отдан наружу")
        return cls(
            id=movie.id,
            title=movie.title,
            description=movie.description,
            category=movie.category,
            poster_url=movie.poster_url,
            year=movie.year,
            rating=movie.rating,
        )
