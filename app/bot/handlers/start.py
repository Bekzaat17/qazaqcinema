"""Команда /start — приветствие + кнопка открытия Web App."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from dishka import FromDishka
from dishka.integrations.aiogram import inject

from app.bot.keyboards.common import webapp_keyboard
from app.config.settings import AppConfig

router = Router(name="start")

GREETING = (
    "Сәлем! 🎬\n\n"
    "QazaqCinema — қазақша дубляжбен сирек мультфильмдер мен аниме.\n"
    "Кинотеатрды ашу үшін төмендегі батырманы бас 👇"
)


@router.message(CommandStart())
@inject
async def handle_start(message: Message, config: FromDishka[AppConfig]) -> None:
    await message.answer(GREETING, reply_markup=webapp_keyboard(config.bot.webapp_url))
