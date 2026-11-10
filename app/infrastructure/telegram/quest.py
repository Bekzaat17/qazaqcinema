from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


class AiogramQuestChannelPublisher:
    def __init__(self, bot: Bot, channel_id: int, bot_username: str) -> None:
        self._bot = bot
        self._channel_id = channel_id
        self._keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🏡 Ауылымды дамыту", url=f"https://t.me/{bot_username}?startapp=quest"
                    ),
                ]
            ]
        )

    @property
    def channel_id(self) -> int:
        return self._channel_id

    async def send(self, text: str) -> int | None:
        try:
            message = await self._bot.send_message(
                self._channel_id, text, parse_mode="HTML", reply_markup=self._keyboard
            )
            return message.message_id
        except TelegramAPIError:
            logger.exception("Рейтинг QazaqQuest не опубликован")
            return None

    async def update(self, message_id: int, text: str) -> None:
        try:
            await self._bot.edit_message_text(
                text,
                chat_id=self._channel_id,
                message_id=message_id,
                parse_mode="HTML",
                reply_markup=self._keyboard,
            )
        except TelegramBadRequest as exc:
            if "message is not modified" not in exc.message.lower():
                logger.warning("Пост рейтинга нельзя обновить: %s", exc.message)
        except TelegramAPIError:
            logger.exception("Обновление рейтинга QazaqQuest не доставлено")
