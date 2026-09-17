"""Сборка aiogram Dispatcher + подключение DI (dishka)."""

from __future__ import annotations

from aiogram import Dispatcher
from dishka import AsyncContainer
from dishka.integrations.aiogram import setup_dishka

from app.bot.handlers import (
    add_movie,
    broadcast,
    daily,
    fallback,
    inline_query,
    milestone,
    moderation,
    quiz,
    stars,
    start,
)


def build_dispatcher(container: AsyncContainer) -> Dispatcher:
    dp = Dispatcher()
    dp.include_routers(
        start.router,
        add_movie.router,
        broadcast.router,
        daily.router,
        milestone.router,
        inline_query.router,
        moderation.router,
        quiz.router,
        stars.router,
        # ПОСЛЕДНИМ: ловит то, что не разобрал никто выше (чек в личку вместо Mini App).
        fallback.router,
    )
    setup_dishka(container=container, router=dp)
    return dp
