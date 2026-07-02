"""Модерация чеков Kaspi в админ-чате: ✅ одобрить / ❌ отклонить.

Хендлер тонкий: парсит `request_id` из callback_data и делегирует
`PaymentModerationService` (approve → активация подписки через Фазу 6; reject → отказ).
После обработки правит подпись сообщения-чека и снимает кнопки.
"""

from __future__ import annotations

from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from dishka import FromDishka
from dishka.integrations.aiogram import inject

from app.application.services.moderation_service import (
    ModerationOutcome,
    ModerationResult,
    PaymentModerationService,
)
from app.bot.keyboards.moderation import APPROVE_PREFIX, REJECT_PREFIX

router = Router(name="moderation")

_ALERTS = {
    ModerationOutcome.APPROVED: "✅ Доступ ашылды",
    ModerationOutcome.REJECTED: "❌ Бас тартылды",
    ModerationOutcome.NOT_FOUND: "Өтініш табылмады",
    ModerationOutcome.ALREADY_HANDLED: "Бұл өтініш өңделген",
}
_MARKS = {
    ModerationOutcome.APPROVED: "✅ Расталды",
    ModerationOutcome.REJECTED: "❌ Бас тартылды",
}


def _parse_id(data: str | None, prefix: str) -> int | None:
    if not data:
        return None
    try:
        return int(data.removeprefix(prefix))
    except ValueError:
        return None


async def _finalize(callback: CallbackQuery, result: ModerationResult) -> None:
    await callback.answer(_ALERTS[result.outcome])
    mark = _MARKS.get(result.outcome)
    if mark is not None and isinstance(callback.message, Message):
        base = callback.message.caption or ""
        await callback.message.edit_caption(caption=f"{base}\n\n{mark}", reply_markup=None)


@router.callback_query(F.data.startswith(APPROVE_PREFIX))
@inject
async def approve(
    callback: CallbackQuery, moderation: FromDishka[PaymentModerationService]
) -> None:
    request_id = _parse_id(callback.data, APPROVE_PREFIX)
    if request_id is None:
        await callback.answer("Қате өтініш", show_alert=True)
        return
    result = await moderation.approve(request_id, datetime.now(UTC))
    await _finalize(callback, result)


@router.callback_query(F.data.startswith(REJECT_PREFIX))
@inject
async def reject(
    callback: CallbackQuery, moderation: FromDishka[PaymentModerationService]
) -> None:
    request_id = _parse_id(callback.data, REJECT_PREFIX)
    if request_id is None:
        await callback.answer("Қате өтініш", show_alert=True)
        return
    result = await moderation.reject(request_id, datetime.now(UTC))
    await _finalize(callback, result)
