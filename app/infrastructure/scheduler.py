"""Фоновый планировщик (apscheduler). Главная задача — сброс просроченных подписок.

Скелет: задача регистрируется на фазе «подписки/крон» (PLAN). Будет дёргать
SubscriptionService.expire_due(now) через REQUEST-scope контейнера.
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dishka import AsyncContainer


def build_scheduler(container: AsyncContainer) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    # PLAN: scheduler.add_job(_expire_due_job, "interval", hours=1, args=[container])
    return scheduler
