"""Сборка aiogram Dispatcher + подключение DI (dishka)."""

from __future__ import annotations

from aiogram import Dispatcher
from dishka import AsyncContainer
from dishka.integrations.aiogram import setup_dishka

from app.bot.handlers import (
    add_movie,
    inline_query,
    moderation,
    stars,
    start,
)


def build_dispatcher(container: AsyncContainer) -> Dispatcher:
    dp = Dispatcher()
    dp.include_routers(
        start.router,
        add_movie.router,
        inline_query.router,
        moderation.router,
        stars.router,
    )
    setup_dishka(container=container, router=dp)
    return dp
