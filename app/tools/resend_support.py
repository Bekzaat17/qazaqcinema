"""Повторная отправка известного текста обращения с актуальными админскими кнопками.

python -m app.tools.resend_support <telegram_id> --text '<текст обращения>'
Текст передаётся явно: обращения не хранятся в базе.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from aiogram import Bot

from app.application.ports.repositories import UserRepository
from app.application.services.support_service import SupportService
from app.infrastructure.di.providers import build_container

logger = logging.getLogger(__name__)


async def _run(user_id: int, text: str) -> int:
    container = build_container()
    bot: Bot | None = None
    try:
        bot = await container.get(Bot)
        async with container() as request:
            users = await request.get(UserRepository)
            user = await users.get(user_id)
            if user is None:
                logger.error("Пользователь id %s не найден", user_id)
                return 1
            support = await request.get(SupportService)
            await support.submit(user, text)
            logger.info("Обращение id %s повторно доставлено администраторам", user_id)
            return 0
    finally:
        if bot is not None:
            await bot.session.close()
        await container.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Повторная отправка обращения админам")
    parser.add_argument("user_id", type=int)
    parser.add_argument("--text", required=True)
    args = parser.parse_args()
    sys.exit(asyncio.run(_run(args.user_id, args.text)))


if __name__ == "__main__":
    main()
