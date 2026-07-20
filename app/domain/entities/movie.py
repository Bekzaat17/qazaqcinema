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
    is_featured: bool = False          # показывать на hero главной (курируется админом в /add)
    hero_image_url: str | None = None  # горизонтальный баннер 3:2 для hero (None → фолбэк постер)
    play_count: int = 0                # число просмотров (Фаза 13); сортировка «Танымал»
    created_at: datetime | None = None  # проставляет БД (server_default); None до вставки
    id: int | None = None  # None до вставки в БД
