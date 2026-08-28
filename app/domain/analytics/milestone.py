"""Веха роста: короткая метка «вот тут вкатили фичу» на временной шкале.

Не состояние («текущая модель — X»): в проекте фичи роста накапливаются и работают
ОДНОВРЕМЕННО (подарочный фильм и фильм дня — оба живы прямо сейчас, см. порядок
оснований в `PlaybackService`), а не сменяют друг друга. Одно поле «активная модель»
на дату соврало бы. Вместо этого — лента меток: сравнивать «до/после» человек будет
сам, глядя на `daily_reports` рядом с датами вех.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Milestone:
    id: int
    occurred_at: datetime
    label: str
    created_by: int  # telegram_id админа, добавившего запись — контекст, не гейт
