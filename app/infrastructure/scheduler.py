"""Фоновый планировщик (apscheduler). Две задачи — обе через REQUEST-scope dishka.

1. `expire_due` (15 мин) — гасит просроченные подписки: ACTIVE → EXPIRED + уведомление +
   чистка выданных видео. Доступ к контенту от этого джоба НЕ зависит (`has_active_access`
   считает `expires_at` в реальном времени на каждом запросе) — джоб лишь приводит статус
   и чат в порядок.
2. `purge_stale_videos` (1 час) — сносит выданные видео старше 40 ч. Главный механизм
   защиты контента: Telegram не даёт боту удалить сообщение старше 48 ч, поэтому выдачи
   надо забирать ЗАРАНЕЕ, не дожидаясь конца подписки (см. `VideoRetentionService`).

Джобы дёргают сервисы через REQUEST-scope контейнер (сессия БД + репозитории живут именно
там). Запуск/остановка — в `main.py`.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dishka import AsyncContainer

from app.application.services.subscription_service import SubscriptionService
from app.application.services.video_retention_service import VideoRetentionService

logger = logging.getLogger(__name__)

EXPIRE_INTERVAL_MINUTES = 15
# Раз в час: выдача живёт 40 ч, до потолка Telegram (48 ч) остаётся запас в 8 часов —
# поэтому пропуск даже нескольких прогонов не превращает видео в неудаляемое.
PURGE_VIDEOS_INTERVAL_MINUTES = 60


async def _expire_due_job(container: AsyncContainer) -> None:
    async with container() as request_container:
        service = await request_container.get(SubscriptionService)
        count = await service.expire_due(datetime.now(UTC))
    if count:
        logger.info("Подписка истекла у %d пользователей → EXPIRED", count)


async def _purge_stale_videos_job(container: AsyncContainer) -> None:
    async with container() as request_container:
        service = await request_container.get(VideoRetentionService)
        # Пачками внутри; число разобранных логирует сам сервис.
        await service.purge_stale(datetime.now(UTC))


def build_scheduler(container: AsyncContainer) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _expire_due_job,
        "interval",
        minutes=EXPIRE_INTERVAL_MINUTES,
        args=[container],
        id="expire_due",
    )
    scheduler.add_job(
        _purge_stale_videos_job,
        "interval",
        minutes=PURGE_VIDEOS_INTERVAL_MINUTES,
        args=[container],
        id="purge_stale_videos",
    )
    return scheduler
