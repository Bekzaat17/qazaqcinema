"""aiogram-адаптеры музыки: отправка аудио в личку и копия в канал-архив."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.types import InputMediaAudio

from app.application.ports.telegram import (
    RecipientUnreachableError,
    TelegramTemporarilyUnavailableError,
)

logger = logging.getLogger(__name__)

_T = TypeVar("_T")



class AiogramAudioSender:
    """Аудио в личку без `protect_content`: музыку можно пересылать — так она и растёт."""

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def _call(self, chat_id: int, send: Callable[[], Awaitable[_T]]) -> _T:
        # Тот же разбор исходов, что у выдачи видео: флуд-лимит пережидаем один раз,
        # закрытый чат и временный сбой — разные исключения порта, а не 500.
        for attempt in (1, 2):
            try:
                return await send()
            except TelegramForbiddenError as exc:
                raise RecipientUnreachableError(str(exc)) from exc
            except TelegramRetryAfter as exc:
                if attempt == 2:
                    raise TelegramTemporarilyUnavailableError(str(exc)) from exc
                await asyncio.sleep(exc.retry_after + 1)
            except (TelegramNetworkError, TelegramServerError) as exc:
                logger.warning("Временный сбой отправки аудио в чат %s: %s", chat_id, exc)
                raise TelegramTemporarilyUnavailableError(str(exc)) from exc
            except TelegramBadRequest as exc:
                if "chat not found" in str(exc).lower():
                    raise RecipientUnreachableError(str(exc)) from exc
                raise
        raise TelegramTemporarilyUnavailableError("не удалось отправить аудио")

    async def send_audio(self, chat_id: int, file_id: str, caption: str) -> int:
        async def send() -> int:
            message = await self._bot.send_audio(
                chat_id, file_id, caption=caption, parse_mode="HTML"
            )
            return message.message_id

        return await self._call(chat_id, send)

    async def send_audio_album(self, chat_id: int, file_ids: Sequence[str], caption: str) -> int:
        if not file_ids:
            return 0
        if len(file_ids) == 1:
            await self.send_audio(chat_id, file_ids[0], caption)
            return 1
        # Подпись — у последнего трека альбома: Telegram показывает её под всей пачкой.
        media = [
            InputMediaAudio(
                media=file_id,
                caption=caption if index == len(file_ids) - 1 else None,
                parse_mode="HTML",
            )
            for index, file_id in enumerate(file_ids)
        ]

        async def send() -> int:
            messages = await self._bot.send_media_group(chat_id, list(media))
            return len(messages)

        return await self._call(chat_id, send)


class AiogramMusicArchive:
    """Копия трека в приватный канал-архив. Канал не настроен или сбой → `None`.

    Fail-open: архив — страховка, а не условие. Трек без копии всё равно попадает в
    каталог (file_id у бота остаётся рабочим), просто без второй точки хранения.
    """

    def __init__(self, bot: Bot, channel_id: int) -> None:
        self._bot = bot
        self._channel_id = channel_id

    async def store(self, file_id: str, caption: str) -> int | None:
        if not self._channel_id:
            return None
        try:
            message = await self._bot.send_audio(
                self._channel_id, file_id, caption=caption[:1000], disable_notification=True
            )
        except TelegramAPIError:
            logger.exception("Трек не скопирован в музыкальный архив")
            return None
        return message.message_id
