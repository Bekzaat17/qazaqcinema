"""Чистый расчёт срока окончания подписки.

Если у юзера ещё активна подписка — новый тариф продлевает её (от текущего
`expires_at`), иначе считаем от текущего момента. Вынесено отдельной функцией,
чтобы покрыть юнит-тестом без БД и переиспользовать в SubscriptionService.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.tariffs.tariff import Tariff


def compute_expiry(now: datetime, tariff: Tariff, current_expires_at: datetime | None) -> datetime:
    base = current_expires_at if current_expires_at and current_expires_at > now else now
    return base + tariff.duration
