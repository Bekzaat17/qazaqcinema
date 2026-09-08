"""Адаптер публикации в публичный канал поверх aiogram Bot (реализует `ChannelPublisher`).

Канал не настроен (`BOT_PUBLIC_CHANNEL_ID` пуст/0) → каждая публикация тихий no-op.
Это тот же приём «по заполненности env», что у способов оплаты Kaspi: доступность
выводится из конфига, а не из отдельного флага «постить ли». Поэтому ни в сервисах, ни
в джобах нет условия «если канал есть» — локальная разработка и тесты просто идут без
канала, ничего не отключая руками.

Фото — всегда С ДИСКА (`photo_path` + `FSInputFile`, см. `telegram/media.py`; корень —
`MediaConfig.root`, домен путь до диска не знает): и карточки контента, и постеры фильмов.
"""

from __future__ import annotations

import logging
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.application.ports.channel import ChannelPost
from app.infrastructure.telegram.media import photo_from_disk

logger = logging.getLogger(__name__)


def _keyboard(post: ChannelPost) -> InlineKeyboardMarkup | None:
    """Кнопка-ССЫЛКА (не `web_app`: канал не примет, см. порт) либо ряд callback-вариантов."""
    if post.choices:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=c.text, callback_data=c.data) for c in post.choices]
            ]
        )
    if not (post.button_text and post.button_url):
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=post.button_text, url=post.button_url)]
        ]
    )


class AiogramChannelPublisher:
    def __init__(self, bot: Bot, channel_id: int, media_root: str) -> None:
        self._bot = bot
        self._channel_id = channel_id
        self._media_root = Path(media_root)

    async def publish(self, post: ChannelPost) -> int | None:
        if not self._channel_id:
            # Канал не настроен — это НЕ ошибка (dev/test живут без него).
            logger.debug("Публичный канал не настроен, пост пропущен")
            return None
        keyboard = _keyboard(post)
        photo = photo_from_disk(self._media_root, post.photo_path)
        try:
            if photo is not None:
                try:
                    sent: Message = await self._bot.send_photo(
                        self._channel_id,
                        photo,
                        caption=post.text,
                        parse_mode="HTML",
                        reply_markup=keyboard,
                        reply_to_message_id=post.reply_to_message_id,
                    )
                    return sent.message_id
                except TelegramBadRequest:
                    # Битый файл либо подпись длиннее лимита. Пост важнее картинки —
                    # уходим текстом, как это делает `send_broadcast`.
                    logger.warning("Фото %s не ушло в канал, публикуем текстом", photo.path)
            sent = await self._bot.send_message(
                self._channel_id,
                post.text,
                parse_mode="HTML",
                reply_markup=keyboard,
                reply_to_message_id=post.reply_to_message_id,
                # Ссылка в тексте не должна разворачиваться в превью: под постом уже есть
                # постер и кнопка, а второй блок со ссылкой ломает вид ленты.
                disable_web_page_preview=True,
            )
            return sent.message_id
        except TelegramAPIError:
            # Бота убрали из админов канала, канал удалён, флуд-лимит. Витрина не имеет
            # права уронить `/add` или джоб — логируем и отдаём None.
            logger.warning("Пост в канал %s не опубликован", self._channel_id, exc_info=True)
            return None

    async def remove_buttons(self, message_id: int) -> bool:
        if not self._channel_id:
            return False
        try:
            await self._bot.edit_message_reply_markup(
                chat_id=self._channel_id, message_id=message_id, reply_markup=None
            )
            return True
        except TelegramAPIError:
            logger.warning("Кнопки с поста %s не сняты", message_id, exc_info=True)
            return False

    async def delete(self, message_id: int) -> bool:
        if not self._channel_id:
            return False
        try:
            return bool(await self._bot.delete_message(self._channel_id, message_id))
        except TelegramAPIError:
            logger.warning("Пост %s из канала не удалён", message_id, exc_info=True)
            return False
