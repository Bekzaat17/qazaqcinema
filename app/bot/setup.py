"""Сборка aiogram Dispatcher + подключение DI (dishka)."""

from __future__ import annotations

from aiogram import Dispatcher
from dishka import AsyncContainer
from dishka.integrations.aiogram import setup_dishka

from app.bot.handlers import channel_post, inline_query, moderation, start


def build_dispatcher(container: AsyncContainer) -> Dispatcher:
    dp = Dispatcher()
    dp.include_routers(
        start.router,
        channel_post.router,
        inline_query.router,
        moderation.router,
    )
    setup_dishka(container=container, router=dp)
    return dp
