"""Клавиатура модерации чека: ✅ одобрить / ❌ отклонить.

Номер чека (`request_id`) вынесен в ТЕКСТ кнопок — чтобы в общем админ-чате, где чеки
идут стопкой, каждая пара кнопок читалась вместе со своим чеком (тот же «№N» в подписи),
и админ не путал, какая кнопка к какому чеку. В callback_data — тот же id (связь строгая).
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

APPROVE_PREFIX = "pay:approve:"
REJECT_PREFIX = "pay:reject:"


def moderation_keyboard(request_id: int, *, access_open: bool = True) -> InlineKeyboardMarkup:
    """Кнопки под чеком. Подписи зависят от того, открыт ли доступ УЖЕ.

    Обычно открыт (`PaymentService` выдаёт его на загрузке чека), и тогда кнопки значат
    «оставить» и «забрать», а не «выдать» и «не выдать». Подпись обязана говорить правду:
    «бас тарту» под работающей подпиской не даёт понять, что нажатие её отключает.
    """
    approve = "дұрыс" if access_open else "ашу"
    reject = "жабу" if access_open else "бас тарту"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"✅ №{request_id} {approve}",
                    callback_data=f"{APPROVE_PREFIX}{request_id}",
                ),
                InlineKeyboardButton(
                    text=f"❌ №{request_id} {reject}",
                    callback_data=f"{REJECT_PREFIX}{request_id}",
                ),
            ]
        ]
    )
