"""Клавиатуры визарда /add: выбор категории + подтверждение."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.domain.catalog.categories import all_categories

CATEGORY_PREFIX = "addcat:"
CONFIRM = "addmovie:confirm"
CANCEL = "addmovie:cancel"


def category_keyboard() -> InlineKeyboardMarkup:
    """Кнопки категорий из справочника (данные → UI; новая категория = +1 запись)."""
    rows = [
        [
            InlineKeyboardButton(
                text=category.title_ru,
                callback_data=f"{CATEGORY_PREFIX}{category.slug}",
            )
        ]
        for category in all_categories()
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Сақтау", callback_data=CONFIRM),
                InlineKeyboardButton(text="❌ Болдырмау", callback_data=CANCEL),
            ]
        ]
    )
