"""Фоновый планировщик (apscheduler). Главная задача — сброс просроченных подписок.

Джоб дёргает `SubscriptionService.expire_due(now)` через REQUEST-scope контейнер dishka
(сессия БД + репозитории живут именно там). Запуск/остановка — в `main.py`.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dishka import AsyncContainer

from app.application.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)

EXPIRE_INTERVAL_MINUTES = 15


async def _expire_due_job(container: AsyncContainer) -> None:
    async with container() as request_container:
        service = await request_container.get(SubscriptionService)
        count = await service.expire_due(datetime.now(UTC))
    if count:
        logger.info("Подписка истекла у %d пользователей → EXPIRED", count)


def build_scheduler(container: AsyncContainer) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _expire_due_job,
        "interval",
        minutes=EXPIRE_INTERVAL_MINUTES,
        args=[container],
        id="expire_due",
    )
    return scheduler
