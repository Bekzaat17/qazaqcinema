"""Кнопка для ответа автору обращения или чека из админской карточки."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

REPLY_PREFIX = "support:reply:"
GRANT_PREFIX = "support:grant:"


def contact_keyboard(telegram_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✉️ Ответить через бота",
                    callback_data=f"{REPLY_PREFIX}{telegram_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔓 Открыть на день",
                    callback_data=f"{GRANT_PREFIX}{telegram_id}:1_day",
                ),
                InlineKeyboardButton(
                    text="🔓 Открыть на месяц",
                    callback_data=f"{GRANT_PREFIX}{telegram_id}:1_month",
                ),
            ],
        ]
    )
