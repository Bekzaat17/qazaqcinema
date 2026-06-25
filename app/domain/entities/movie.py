"""Сущность «Фильм» — POPO, без внешних зависимостей."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Movie:
    title: str
    description: str
    category: str         # slug категории; справочник — domain/catalog/categories.py
    poster_url: str
    telegram_file_id: str  # ВНУТРЕННЕЕ: уходит только боту, НИКОГДА на фронтенд
    year: int | None = None
    rating: float | None = None
    id: int | None = None  # None до вставки в БД
