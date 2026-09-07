"""Адаптер группы обсуждений поверх aiogram Bot (реализует `DiscussionGroup`).

Группа не настроена (`BOT_DISCUSSION_GROUP_ID=0`) → no-op, как у канала. Удаление требует
у бота права «Delete messages» в группе; нет права → TelegramAPIError → False + лог, ответ
человека при этом уже записан — просто останется виден.
"""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)


class AiogramDiscussionGroup:
    def __init__(self, bot: Bot, group_id: int) -> None:
        self._bot = bot
        self._group_id = group_id

    async def delete_message(self, message_id: int) -> bool:
        if not self._group_id:
            return False
        try:
            return bool(await self._bot.delete_message(self._group_id, message_id))
        except TelegramAPIError:
            logger.warning("Комментарий %s в группе не удалён", message_id, exc_info=True)
            return False

    async def reply_in_thread(self, thread_message_id: int, text: str) -> bool:
        if not self._group_id:
            return False
        try:
            await self._bot.send_message(
                self._group_id,
                text,
                parse_mode="HTML",
                reply_to_message_id=thread_message_id,
                disable_web_page_preview=True,
            )
            return True
        except TelegramAPIError:
            logger.warning("Ответ в ветку %s не отправлен", thread_message_id, exc_info=True)
            return False
