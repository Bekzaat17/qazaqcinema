"""DTO фильма для фронтенда. telegram_file_id НЕ отдаётся наружу (security)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.domain.entities.movie import Movie


class MovieOut(BaseModel):
    id: int
    title_kk: str                      # основное название (казахское)
    title_ru: str | None = None
    title_original: str | None = None
    description: str
    categories: list[str]
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
            title_kk=movie.title_kk,
            title_ru=movie.title_ru,
            title_original=movie.title_original,
            description=movie.description,
            categories=movie.categories,
            poster_url=movie.poster_url,
            year=movie.year,
            rating=movie.rating,
        )


class PlayOut(BaseModel):
    """Ответ `/play`: видео отправлено в чат пользователя с ботом (не через HTTP)."""

    status: Literal["sent"]
    # Видео ушло за счёт подарочного фильма → фронт показывает модалку с подарком, а не
    # обычную «видео жіберілді». Отдельное поле, а не второй `status`: доставка состоялась
    # в обоих случаях, различается лишь основание.
    gift: bool = False
    # Видео ушло как бесплатный фильм дня. От `gift` отличается принципиально: подарок
    # одноразовый и потрачен, а тут не потрачено ничего — фронт не должен ни перечитывать
    # состояние подарка, ни говорить «сыйлық жұмсалды».
    daily: bool = False


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

    # Hero = фильм дня (решение 2026-08-19): первый экран показывает то, что сегодня
    # можно посмотреть бесплатно, а не просто красивую карточку.
    hero: MovieOut | None = None
    # До какого момента hero бесплатен — ближайшая местная полночь (Asia/Almaty). Считает
    # бэк: правило суток живёт в `domain/catalog/daily`, и отсчёт на экране обязан
    # сходиться с тем, что реально пустит `PlaybackService`.
    hero_free_until: datetime | None = None
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
