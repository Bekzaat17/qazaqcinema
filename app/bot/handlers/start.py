"""Команда /start — приветствие + кнопка открытия Web App."""

from __future__ import annotations

import re

from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
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

# Deep-link с SEO-страницы: /start m_<id> → открыть Mini App сразу на нужном фильме.
_START_MOVIE = re.compile(r"^m_?(\d+)$")


@router.message(CommandStart())
@inject
async def handle_start(
    message: Message, command: CommandObject, config: FromDishka[AppConfig]
) -> None:
    # payload после /start (t.me/<bot>?start=m_<id>). Совпало — добавляем #m<id> к URL Web App,
    # чтобы Mini App открыл карточку фильма (фолбэк к прямому ?startapp=, см. web/lib/telegram).
    url = config.bot.webapp_url
    match = _START_MOVIE.match(command.args or "")
    if match and url:
        url = f"{url}#m{match.group(1)}"
    await message.answer(GREETING, reply_markup=webapp_keyboard(url))
