"""Общие клавиатуры бота."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo


def webapp_keyboard(url: str) -> InlineKeyboardMarkup:
    """Кнопка открытия Web App (🍿 Кинотеатрды ашу)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🍿 Кинотеатрды ашу", web_app=WebAppInfo(url=url))]
        ]
    )
