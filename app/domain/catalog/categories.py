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
    # Тип / формат
    "disney": Category("disney", "Мультфильмы", "Мультфильмдер"),
    "anime": Category("anime", "Аниме", "Аниме"),
    "film": Category("film", "Фильмы", "Фильмдер"),
    "serial": Category("serial", "Сериалы", "Сериалдар"),
    "short": Category("short", "Короткометражки", "Қысқа метр"),
    "documentary": Category("documentary", "Документальные", "Деректі"),
    # Происхождение
    "otandyq": Category("otandyq", "Отечественные", "Отандық"),
    # Аудитория
    "kids": Category("kids", "Детские", "Балаларға"),
    "girls": Category("girls", "Для девочек", "Қыздарға"),
    "boys": Category("boys", "Для мальчиков", "Ұлдарға"),
    "family": Category("family", "Семейные", "Отбасылық"),
    # Жанр
    "adventure": Category("adventure", "Приключения", "Шытырман оқиға"),
    "comedy": Category("comedy", "Комедии", "Күлкілі"),
    "fantasy": Category("fantasy", "Фэнтези", "Қиял-ғажайып"),
    "fairytale": Category("fairytale", "Сказки", "Ертегілер"),
    "learning": Category("learning", "Развивающие", "Білім беру"),
    # Тематические
    "classic": Category("classic", "Классика", "Классика"),
}


def get_category(slug: str) -> Category | None:
    return CATEGORIES.get(slug)


def is_known_category(slug: str) -> bool:
    return slug in CATEGORIES


def all_categories() -> list[Category]:
    return list(CATEGORIES.values())
