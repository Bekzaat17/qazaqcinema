"""DTO результата парсинга подписи поста из канала-архива."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ParsedMovie:
    title: str
    category: str
    description: str
    poster_url: str
    year: int | None = None
    rating: float | None = None
