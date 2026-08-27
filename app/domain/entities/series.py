"""Сущность «Сериал» — POPO, без внешних зависимостей.

Сериал сам по себе — только название: он существует лишь как группировка сезонов в
визарде `/add` (список кнопками «выбери сериал») и в каталоге (карточка-хаб). Постер,
категории и описание живут на уровне сезона/серии — см. `Season` и `domain/entities/movie`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Series:
    title_kk: str
    created_at: datetime | None = None  # проставляет БД; None до вставки
    id: int | None = None
