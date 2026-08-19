"""Команда /start — приветствие + кнопка открытия Web App."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message
from dishka import FromDishka
from dishka.integrations.aiogram import inject

from app.application.services.activity_service import UserActivityService
from app.bot.keyboards.common import webapp_keyboard
from app.config.settings import AppConfig

logger = logging.getLogger(__name__)

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
    message: Message,
    command: CommandObject,
    config: FromDishka[AppConfig],
    activity: FromDishka[UserActivityService],
) -> None:
    # Фиксируем контакт: до этого юзер попадал в БД только открыв Mini App, и нажавшие
    # /start (в т.ч. пришедшие из поиска/SEO) в статистике не существовали.
    # Под try/except намеренно: приветствие — основной сценарий команды, и недоступная
    # БД не должна оставлять человека вообще без ответа (то же правило, что у авто-рассылки
    # новинок в `MovieIngestionService.ingest`).
    if message.from_user is not None:
        try:
            await activity.register_start(
                message.from_user.id, message.from_user.username, datetime.now(UTC)
            )
        except Exception:
            logger.exception("Не удалось зафиксировать /start юзера %s", message.from_user.id)
    # payload после /start (t.me/<bot>?start=m_<id>). Совпало — добавляем #m<id> к URL Web App,
    # чтобы Mini App открыл карточку фильма (фолбэк к прямому ?startapp=, см. web/lib/telegram).
    url = config.bot.webapp_url
    match = _START_MOVIE.match(command.args or "")
    if match and url:
        url = f"{url}#m{match.group(1)}"
    await message.answer(GREETING, reply_markup=webapp_keyboard(url))
