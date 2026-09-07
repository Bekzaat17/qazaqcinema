"""Адаптер публикации в публичный канал поверх aiogram Bot (реализует `ChannelPublisher`).

Канал не настроен (`BOT_PUBLIC_CHANNEL_ID` пуст/0) → каждая публикация тихий no-op.
Это тот же приём «по заполненности env», что у способов оплаты Kaspi: доступность
выводится из конфига, а не из отдельного флага «постить ли». Поэтому ни в сервисах, ни
в джобах нет условия «если канал есть» — локальная разработка и тесты просто идут без
канала, ничего не отключая руками.
"""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.application.ports.channel import ChannelPost

logger = logging.getLogger(__name__)


def _keyboard(post: ChannelPost) -> InlineKeyboardMarkup | None:
    """Кнопка-ССЫЛКА (не `web_app`): Web App-кнопку канал не примет (см. порт)."""
    if not (post.button_text and post.button_url):
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=post.button_text, url=post.button_url)]
        ]
    )


class AiogramChannelPublisher:
    def __init__(self, bot: Bot, channel_id: int) -> None:
        self._bot = bot
        self._channel_id = channel_id

    async def publish(self, post: ChannelPost) -> bool:
        if not self._channel_id:
            # Канал не настроен — это НЕ ошибка (dev/test живут без него).
            logger.debug("Публичный канал не настроен, пост пропущен")
            return False
        keyboard = _keyboard(post)
        try:
            if post.photo_url is not None:
                try:
                    await self._bot.send_photo(
                        self._channel_id,
                        post.photo_url,
                        caption=post.text,
                        parse_mode="HTML",
                        reply_markup=keyboard,
                    )
                    return True
                except TelegramBadRequest:
                    # Telegram не смог забрать постер по URL (домен недоступен снаружи,
                    # битый файл) либо подпись длиннее лимита. Пост важнее картинки —
                    # уходим текстом, как это делает `send_broadcast`.
                    logger.warning(
                        "Постер %s не ушёл в канал, публикуем текстом", post.photo_url
                    )
            await self._bot.send_message(
                self._channel_id,
                post.text,
                parse_mode="HTML",
                reply_markup=keyboard,
                # Ссылка в тексте не должна разворачиваться в превью: под постом уже есть
                # постер и кнопка, а второй блок со ссылкой ломает вид ленты.
                disable_web_page_preview=True,
            )
            return True
        except TelegramAPIError:
            # Бота убрали из админов канала, канал удалён, флуд-лимит. Витрина не имеет
            # права уронить `/add` или джоб — логируем и отдаём False.
            logger.warning("Пост в канал %s не опубликован", self._channel_id, exc_info=True)
            return False
