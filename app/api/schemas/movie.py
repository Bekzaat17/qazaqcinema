"""DTO фильма для фронтенда. telegram_file_id НЕ отдаётся наружу (security)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.domain.entities.movie import Movie


class MovieOut(BaseModel):
    id: int
    title_kk: str                      # основное название (казахское)
    title_ru: str | None = None
    title_original: str | None = None
    description: str
    category: str
    poster_url: str
    year: int | None = None
    rating: float | None = None
    hero_image_url: str | None = None  # горизонтальный баннер, если фильм показан на hero
    # telegram_file_id ОТСУТСТВУЕТ намеренно — его видит только бот.

    @classmethod
    def from_domain(cls, movie: Movie) -> MovieOut:
        if movie.id is None:
            raise ValueError("movie без id не может быть отдан наружу")
        return cls(
            id=movie.id,
            title_kk=movie.title_kk,
            title_ru=movie.title_ru,
            title_original=movie.title_original,
            description=movie.description,
            category=movie.category,
            poster_url=movie.poster_url,
            year=movie.year,
            rating=movie.rating,
            hero_image_url=movie.hero_image_url,
        )


class PlayOut(BaseModel):
    """Ответ `/play`: видео отправлено в чат пользователя с ботом (не через HTTP)."""

    status: Literal["sent"]


class ShelfOut(BaseModel):
    """Готовая полка главной: ключ, казахская подпись и фильмы (собрано на бэке, Фаза 13)."""

    key: str            # fresh | popular | ...
    title: str          # казахская подпись полки
    movies: list[MovieOut]


class CatalogHomeOut(BaseModel):
    """Агрегат главного экрана (Фаза 13): hero + готовые полки. Кэшируется cache-aside.

    Размер ответа = O(полки × N), НЕ O(каталог): сервер режет каждую полку до N (14) —
    фронт получает ровно то, что рисует, ответ не растёт с ростом каталога.
    """

    hero: MovieOut | None = None
    shelves: list[ShelfOut]


class MoviePageOut(BaseModel):
    """Страница каталога (Фаза 13): срез + метаданные пагинации. file_id так же скрыт."""

    items: list[MovieOut]
    total: int
    page: int
    limit: int
    has_more: bool


class CategoryCountOut(BaseModel):
    """Непустая категория со счётчиком — для чипов-фильтра каталога (Фаза 13)."""

    slug: str
    count: int
