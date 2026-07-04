"""Справочник категорий.

Хранится как данные (dict), а не как жёсткий enum: категория в БД — обычный VARCHAR,
поэтому добавить категорию = одна строка здесь, без миграции и без правок логики.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Category:
    slug: str
    title_ru: str
    title_kk: str


CATEGORIES: dict[str, Category] = {
    "disney": Category("disney", "Мультфильмы", "Мультфильмдер"),
    "anime": Category("anime", "Аниме", "Аниме"),
    "film": Category("film", "Фильмы", "Фильмдер"),
    "serial": Category("serial", "Сериалы", "Сериалдар"),
    "otandyq": Category("otandyq", "Отечественные", "Отандық"),
    "kids": Category("kids", "Детские", "Балаларға"),
}


def get_category(slug: str) -> Category | None:
    return CATEGORIES.get(slug)


def is_known_category(slug: str) -> bool:
    return slug in CATEGORIES


def all_categories() -> list[Category]:
    return list(CATEGORIES.values())
