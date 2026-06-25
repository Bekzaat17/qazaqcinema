"""Тариф — неизменяемое value object."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True, slots=True)
class Tariff:
    slug: str
    title_ru: str
    title_kk: str
    price_kzt: int
    duration: timedelta
    recurring: bool = False  # True → пригоден для авто-подписки (Telegram Stars, помесячно)
