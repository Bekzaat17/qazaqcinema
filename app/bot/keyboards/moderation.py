"""Клавиатура модерации чека: ✅ одобрить / ❌ отклонить.

Номер чека (`request_id`) вынесен в ТЕКСТ кнопок — чтобы в общем админ-чате, где чеки
идут стопкой, каждая пара кнопок читалась вместе со своим чеком (тот же «№N» в подписи),
и админ не путал, какая кнопка к какому чеку. В callback_data — тот же id (связь строгая).
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

APPROVE_PREFIX = "pay:approve:"
REJECT_PREFIX = "pay:reject:"


def moderation_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"✅ №{request_id} ашу",
                    callback_data=f"{APPROVE_PREFIX}{request_id}",
                ),
                InlineKeyboardButton(
                    text=f"❌ №{request_id} бас тарту",
                    callback_data=f"{REJECT_PREFIX}{request_id}",
                ),
            ]
        ]
    )
