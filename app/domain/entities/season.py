"""Сущность «Сезон» — POPO, без внешних зависимостей.

Сезон несёт ровно то, что не нужно спрашивать заново на каждую серию (решение
2026-08-28): постер, название, категории, описание — как у обычного фильма при
создании. Серии внутри сезона своего названия не имеют — это просто номер (1, 2, 3…),
`Movie.episode_number`; название/категории/описание им при сохранении копируются
отсюда (см. `MovieIngestionService.ingest`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Season:
    series_id: int
    season_number: int
    poster_url: str
    title_kk: str
    description: str
    categories: list[str]
    created_at: datetime | None = None  # проставляет БД; None до вставки
    id: int | None = None
