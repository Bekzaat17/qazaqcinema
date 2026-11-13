"""CLI после push, деплоя и seed: один анонс с кнопкой, затем закрепление.

    python -m app.tools.announce_riddles --publish

Запускать ВНУТРИ работающего обновлённого контейнера бота. Повторный запуск находит
пост по журналу и повторяет только закрепление. Без --publish ничего не отправляет.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import UTC, datetime

from aiogram import Bot

from app.application.services.riddle_announcement_service import RiddleAnnouncementService
from app.infrastructure.di.providers import build_container

logger = logging.getLogger(__name__)


async def _run() -> int:
    container = build_container()
    bot = await container.get(Bot)
    try:
        async with container() as request:
            service = await request.get(RiddleAnnouncementService)
            outcome = await service.publish_and_pin(datetime.now(UTC))
            logger.info("%s message_id=%s", outcome.text, outcome.message_id)
            return 0 if outcome.pinned else 1
    finally:
        await bot.session.close()
        await container.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Опубликовать и закрепить анонс жұмбақ дня")
    parser.add_argument("--publish", action="store_true", help="отправить в публичный канал")
    args = parser.parse_args()
    if args.publish:
        raise SystemExit(asyncio.run(_run()))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
