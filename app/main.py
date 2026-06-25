"""Точка входа бота (polling для локальной разработки).

Прод (webhook + Nginx) — отдельная фаза (PLAN). API запускается отдельно:
    uvicorn app.api.app:app
"""

from __future__ import annotations

import asyncio

from aiogram import Bot

from app.bot.setup import build_dispatcher
from app.infrastructure.di.providers import build_container


async def main() -> None:
    container = build_container()
    bot = await container.get(Bot)
    dispatcher = build_dispatcher(container)
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())
