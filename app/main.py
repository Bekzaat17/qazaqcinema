"""Точка входа бота (polling для локальной разработки).

Прод (webhook + Nginx) — отдельная фаза (PLAN). API запускается отдельно:
    uvicorn app.api.app:app
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from redis.asyncio import Redis

from app.bot.setup import build_dispatcher
from app.infrastructure.di.providers import build_container
from app.infrastructure.scheduler import build_scheduler

_log = logging.getLogger("qazaqcinema.bot")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    container = build_container()
    bot = await container.get(Bot)
    try:
        redis = await container.get(Redis)
        await redis.ping()
        _log.info("Redis подключён")
    except Exception as exc:
        _log.warning("Redis недоступен на старте (fail-open): %s", exc)
    dispatcher = build_dispatcher(container)
    scheduler = build_scheduler(container)
    scheduler.start()
    try:
        await dispatcher.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())
