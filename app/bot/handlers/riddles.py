"""Кнопка в канале и команды в группе обсуждений; личка не участвует."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from dishka import FromDishka
from dishka.integrations.aiogram import inject

from app.application.ports.discussion import DiscussionGroup
from app.application.services.daily_riddle_service import DailyRiddleService, RiddleReply
from app.application.services.quiz_service import Answerer
from app.config.settings import AppConfig
from app.domain.channel.content.daily_riddle import DAILY_RIDDLE_CALLBACK

router = Router(name="riddles")
logger = logging.getLogger(__name__)


def _in_group(message: Message, config: AppConfig) -> bool:
    group_id = config.bot.discussion_group_id
    return bool(group_id) and message.chat.id == group_id


def _post_url(config: AppConfig, message_id: int) -> str:
    return f"https://t.me/c/{str(config.bot.public_channel_id).removeprefix('-100')}/{message_id}"


async def _reply(message: Message, outcome: RiddleReply, config: AppConfig) -> None:
    text = escape(outcome.text)
    if outcome.message_id is not None:
        text += f'\n<a href="{_post_url(config, outcome.message_id)}">Каналда ашу →</a>'
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)


@router.callback_query(F.data == DAILY_RIDDLE_CALLBACK)
@inject
async def riddle_button(
    callback: CallbackQuery, config: FromDishka[AppConfig], riddles: FromDishka[DailyRiddleService],
) -> None:
    message = callback.message
    if (not isinstance(message, Message) or not config.bot.public_channel_id
            or message.chat.id != config.bot.public_channel_id):
        await callback.answer()
        return
    outcome = await riddles.request(datetime.now(UTC))
    try:
        # Кнопка навсегда остаётся callback: старые афиши тоже открывают СЕГОДНЯШНИЙ день.
        # Текст виден одному нажавшему; дубликат поста в канал не отправляется.
        await callback.answer(outcome.text[:200], show_alert=True)
    except TelegramAPIError:
        logger.warning("Не удалось показать ответ на кнопку жұмбақ", exc_info=True)


@router.message(Command("jumbak"))
@inject
async def riddle_command(
    message: Message, config: FromDishka[AppConfig], riddles: FromDishka[DailyRiddleService],
) -> None:
    if _in_group(message, config):
        await _reply(message, await riddles.request(datetime.now(UTC)), config)


@router.message(Command("answer"))
@inject
async def answer_command(
    message: Message, command: CommandObject, config: FromDishka[AppConfig],
    riddles: FromDishka[DailyRiddleService], group: FromDishka[DiscussionGroup],
) -> None:
    if not _in_group(message, config) or message.from_user is None or message.from_user.is_bot:
        return
    now = datetime.now(UTC)
    if command.args:
        outcome = await riddles.answer(
            Answerer(message.from_user.id, message.from_user.first_name), command.args, now,
            thread_id=message.message_thread_id,
        )
        await group.delete_message(message.message_id)
    else:
        outcome = await riddles.result(now)
    if outcome is not None:
        await _reply(message, outcome, config)


@router.message(Command("rating"))
@inject
async def rating_command(
    message: Message, config: FromDishka[AppConfig], riddles: FromDishka[DailyRiddleService],
) -> None:
    if _in_group(message, config) and message.from_user is not None:
        await message.answer(
            await riddles.rating(message.from_user.id, datetime.now(UTC)), parse_mode="HTML",
        )
