"""Тарифная сетка (данные).

Добавить/изменить тариф = правка этого словаря. Бизнес-логика (расчёт срока,
оплата) не меняется — Open/Closed. `recurring=True` помечает тариф, пригодный
для авто-подписки Telegram Stars (только помесячный период).
"""

from __future__ import annotations

from datetime import timedelta

from app.domain.tariffs.tariff import Tariff

TARIFFS: dict[str, Tariff] = {
    "1_day": Tariff("1_day", "1 день", "1 күн", 349, timedelta(days=1)),
    "1_month": Tariff("1_month", "1 месяц", "1 ай", 1899, timedelta(days=30), recurring=True),
    "3_months": Tariff("3_months", "3 месяца", "3 ай", 4999, timedelta(days=90)),
}


def get_tariff(slug: str) -> Tariff | None:
    return TARIFFS.get(slug)


def all_tariffs() -> list[Tariff]:
    return list(TARIFFS.values())
