"""Фоновый планировщик (apscheduler). Три задачи — все через REQUEST-scope dishka.

1. `expire_due` (15 мин) — гасит просроченные подписки: ACTIVE → EXPIRED + уведомление +
   чистка выданных видео. Доступ к контенту от этого джоба НЕ зависит (`has_active_access`
   считает `expires_at` в реальном времени на каждом запросе) — джоб лишь приводит статус
   и чат в порядок.
2. `purge_stale_videos` (1 час) — сносит выданные видео старше 40 ч. Главный механизм
   защиты контента: Telegram не даёт боту удалить сообщение старше 48 ч, поэтому выдачи
   надо забирать ЗАРАНЕЕ, не дожидаясь конца подписки (см. `VideoRetentionService`).

3. `daily_report` (раз в сутки, 23:00 по Алматы) — короткая сводка админам в личку:
   сколько всего людей, сколько активных подписок, сколько заходов/просмотров за день.

Джобы дёргают сервисы через REQUEST-scope контейнер (сессия БД + репозитории живут именно
там). Запуск/остановка — в `main.py`. Планировщик поднимает ТОЛЬКО процесс бота (api и
worker его не заводят) — поэтому отчёт уходит один раз, сколько бы реплик API ни было.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dishka import AsyncContainer

from app.application.ports.telegram import AdminsUnreachableError, TelegramNotifier
from app.application.services.analytics_service import AnalyticsService
from app.application.services.subscription_service import SubscriptionService
from app.application.services.video_retention_service import VideoRetentionService
from app.domain.analytics.report import render_report

logger = logging.getLogger(__name__)

EXPIRE_INTERVAL_MINUTES = 15
# Раз в час: выдача живёт 40 ч, до потолка Telegram (48 ч) остаётся запас в 8 часов —
# поэтому пропуск даже нескольких прогонов не превращает видео в неудаляемое.
PURGE_VIDEOS_INTERVAL_MINUTES = 60
# Отчёт — данные: когда и по какому времени. Часовой пояс задан ЯВНО (не «время сервера»):
# контейнеры живут в UTC, и без него «23:00» пришло бы в 4 утра по Казахстану.
REPORT_TZ = ZoneInfo("Asia/Almaty")
REPORT_HOUR = 23
REPORT_MINUTE = 0


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


async def _daily_report_job(container: AsyncContainer) -> None:
    async with container() as request_container:
        analytics = await request_container.get(AnalyticsService)
        notifier: TelegramNotifier = await request_container.get(TelegramNotifier)
        report = await analytics.daily_report(datetime.now(UTC), REPORT_TZ)
        try:
            await notifier.notify_admins(render_report(report))
        except AdminsUnreachableError:
            # Никто из админов не получил сводку (не нажал /start / заблокировал бота).
            # Это не повод ронять джоб — цифры не потеряны, они всегда в БД.
            logger.warning("Ежедневный отчёт не доставлен ни одному админу")


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
    scheduler.add_job(
        _daily_report_job,
        CronTrigger(hour=REPORT_HOUR, minute=REPORT_MINUTE, timezone=REPORT_TZ),
        args=[container],
        id="daily_report",
        # Бот перезапустился в 23:05 — отчёт за день всё равно уйдёт (в пределах часа),
        # а не пропадёт до завтра; coalesce не даёт послать его дважды.
        misfire_grace_time=3600,
        coalesce=True,
    )
    return scheduler
