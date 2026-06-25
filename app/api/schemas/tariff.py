"""DTO тарифа для экрана пэйволла."""

from __future__ import annotations

from pydantic import BaseModel

from app.domain.tariffs.tariff import Tariff


class TariffOut(BaseModel):
    slug: str
    title_ru: str
    title_kk: str
    price_kzt: int
    days: int
    recurring: bool

    @classmethod
    def from_domain(cls, tariff: Tariff) -> TariffOut:
        return cls(
            slug=tariff.slug,
            title_ru=tariff.title_ru,
            title_kk=tariff.title_kk,
            price_kzt=tariff.price_kzt,
            days=tariff.duration.days,
            recurring=tariff.recurring,
        )
