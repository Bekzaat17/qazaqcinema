"""Клавиатуры визарда /add: выбор категории + подтверждение."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.domain.catalog.categories import all_categories

CATEGORY_PREFIX = "addcat:"
FEATURED_PREFIX = "addfeat:"
CONFIRM = "addmovie:confirm"
CANCEL = "addmovie:cancel"


def featured_keyboard() -> InlineKeyboardMarkup:
    """«На главную (hero)?» — Иә/Жоқ. Иә → админ пришлёт горизонтальный баннер."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⭐ Иә", callback_data=f"{FEATURED_PREFIX}1"),
                InlineKeyboardButton(text="Жоқ", callback_data=f"{FEATURED_PREFIX}0"),
            ]
        ]
    )


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
