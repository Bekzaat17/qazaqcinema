"""Сущность «Фильм» — POPO, без внешних зависимостей."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Movie:
    title_kk: str          # казахское название — основное (продукт казахоязычный)
    description: str
    categories: list[str]  # slug'и категорий (мультивыбор); см. domain/catalog/categories.py
    poster_url: str        # публичный путь к постеру-статике, напр. /posters/<uuid>.jpg
    telegram_file_id: str  # ВНУТРЕННЕЕ: уходит только боту, НИКОГДА на фронтенд
    title_ru: str | None = None        # русское название (для показа и поиска)
    title_original: str | None = None  # оригинал/EN (для поиска: «Frozen», «Naruto»)
    year: int | None = None
    rating: float | None = None
    # Наследие широкого баннера (до 2026-08-19). Визард его больше НЕ запрашивает и hero
    # его не рисует — широкую поверхность делает фронт из постера. Поле живёт ради SEO:
    # у полусотни старых фильмов горизонтальная картинка лучше как og:image в соцсетях,
    # чем портретный постер (`SeoBuilder`: hero → фолбэк постер).
    hero_image_url: str | None = None
    play_count: int = 0                # число просмотров (Фаза 13); входит в «Танымал»
    favorites_count: int = 0           # сколько раз добавлен в избранное; тоже в «Танымал»
    # Сериалы (решение 2026-08-28): NULL у обоих = обычный самостоятельный фильм. Заполнены
    # оба сразу — строка является серией конкретного сезона (`domain/entities/season.Season`);
    # название/категории/описание у серии свои, как у любого Movie (визард лишь предзаполняет
    # их значениями последней серии сезона, чтобы не печатать заново).
    season_id: int | None = None
    episode_number: int | None = None
    created_at: datetime | None = None  # проставляет БД (server_default); None до вставки
    id: int | None = None  # None до вставки в БД
