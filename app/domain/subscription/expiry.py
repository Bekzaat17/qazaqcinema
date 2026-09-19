"""Чистый расчёт срока окончания подписки.

Если у юзера ещё активна подписка — новый тариф продлевает её (от текущего
`expires_at`), иначе считаем от текущего момента. Вынесено отдельной функцией,
чтобы покрыть юнит-тестом без БД и переиспользовать в SubscriptionService.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.domain.tariffs.tariff import Tariff


def extend(now: datetime, duration: timedelta, current_expires_at: datetime | None) -> datetime:
    """Продлить доступ на `duration`: от текущего срока, если он ещё идёт, иначе от now.

    Отдельно от `compute_expiry`, потому что продлевает не только покупка: подаренные
    дни (компенсация за ожидание модерации) считаются ровно так же, а тарифа за ними нет.
    """
    base = current_expires_at if current_expires_at and current_expires_at > now else now
    return base + duration


def compute_expiry(now: datetime, tariff: Tariff, current_expires_at: datetime | None) -> datetime:
    return extend(now, tariff.duration, current_expires_at)
