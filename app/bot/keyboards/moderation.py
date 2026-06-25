"""Клавиатура модерации чека: ✅ одобрить / ❌ отклонить."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

APPROVE_PREFIX = "pay:approve:"
REJECT_PREFIX = "pay:reject:"


def moderation_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Доступты ашу", callback_data=f"{APPROVE_PREFIX}{request_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Бас тарту", callback_data=f"{REJECT_PREFIX}{request_id}"
                ),
            ]
        ]
    )
