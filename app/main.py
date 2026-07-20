"""Точка входа бота: polling (локально/дев) или webhook (прод) — выбор по схеме PUBLIC_ORIGIN.

http (webhook_url пуст) → `start_polling` (dev). https (webhook_url = PUBLIC_ORIGIN) →
aiohttp-сервер вебхука за Caddy (TLS терминирует Caddy; он проксирует /tg/ → BOT_WEBHOOK_PATH
на этот процесс). Отличие сред — только env (12-factor). API запускается отдельно:
`uvicorn app.api.app:app`.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import MenuButtonWebApp, WebAppInfo
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dishka import AsyncContainer
from redis.asyncio import Redis

from app.bot.setup import build_dispatcher
from app.config.settings import AppConfig
from app.infrastructure.di.providers import build_container
from app.infrastructure.scheduler import build_scheduler

_log = logging.getLogger("qazaqcinema.bot")


async def _ping_redis(container: AsyncContainer) -> None:
    """Health-ping Redis на старте. Fail-open: недоступность не роняет бота."""
    try:
        redis = await container.get(Redis)
        await redis.ping()
        _log.info("Redis подключён")
    except Exception as exc:
        _log.warning("Redis недоступен на старте (fail-open): %s", exc)


async def _setup_menu_button(bot: Bot, config: AppConfig) -> None:
    """Постоянная кнопка-меню (слева у поля ввода) открывает Mini App.

    Так вход в кинотеатр всегда под рукой — не нужно искать /start-сообщение в истории
    чата (среди других сообщений/видео оно уезжает вверх). Устанавливаем дефолтную кнопку
    для всех. Fail-open: Telegram требует HTTPS для web_app — если URL не https (bare
    localhost), молча пропускаем, чтобы не ронять старт бота.
    """
    if not config.bot.webapp_url:
        return
    with contextlib.suppress(Exception):
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="🎬 Кинотеатр",
                web_app=WebAppInfo(url=config.bot.webapp_url),
            )
        )
        _log.info("Кнопка-меню Mini App установлена: %s", config.bot.webapp_url)


async def _run_webhook(bot: Bot, dp: Dispatcher, config: AppConfig) -> None:
    """Прод: aiohttp-сервер вебхука. Telegram POST'ит апдейты на webhook_full_url;
    Caddy (TLS) проксирует их на 0.0.0.0:webhook_port. Секрет-токен валидирует aiogram."""
    secret = config.bot.webhook_secret.get_secret_value() or None
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=secret).register(
        app, path=config.bot.webhook_path
    )
    setup_application(app, dp, bot=bot)
    await bot.set_webhook(
        url=config.bot.webhook_full_url,
        secret_token=secret,
        drop_pending_updates=True,
        allowed_updates=dp.resolve_used_update_types(),
    )
    _log.info("Webhook: %s (слушаю :%d)", config.bot.webhook_full_url, config.bot.webhook_port)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=config.bot.webhook_port)
    await site.start()
    try:
        await asyncio.Event().wait()  # держим процесс до сигнала остановки
    finally:
        await runner.cleanup()


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    container = build_container()
    config = await container.get(AppConfig)
    bot = await container.get(Bot)
    await _ping_redis(container)
    await _setup_menu_button(bot, config)
    dispatcher = build_dispatcher(container)
    scheduler = build_scheduler(container)
    scheduler.start()
    try:
        if config.bot.webhook_url:
            await _run_webhook(bot, dispatcher, config)
        else:
            # Снимаем ранее выставленный webhook, иначе getUpdates отклоняется
            # («can't use getUpdates while webhook is active»). Заодно чистим
            # накопленную очередь недоставленных апдейтов, чтобы не проигрывать старьё.
            await bot.delete_webhook(drop_pending_updates=True)
            _log.info("Polling: webhook снят, слушаю getUpdates")
            await dispatcher.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())
