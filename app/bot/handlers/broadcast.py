"""Бот-команда `/broadcast` — ручная рассылка админа (Фаза 12).

Поток (FSM): `/broadcast` → мәтін → предпросмотр + подтверждение → ставим в очередь.
Тонкая презентация: собственно рассылку (аудитория + очередь) делает `BroadcastService`,
хендлер лишь собирает текст и подтверждает. `/cancel` сбрасывает (общий хендлер /add).

MVP — текст. Медиа-рассылки (фото/видео) можно добавить позже, расширив BroadcastMessage.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from dishka import FromDishka
from dishka.integrations.aiogram import inject

from app.application.services.broadcast_service import BroadcastService
from app.bot.security import is_admin
from app.config.settings import AppConfig

router = Router(name="broadcast")

_SEND = "bcast:send"
_CANCEL = "bcast:cancel"


class Broadcast(StatesGroup):
    text = State()
    confirm = State()


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Жіберу", callback_data=_SEND),
                InlineKeyboardButton(text="❌ Болдырмау", callback_data=_CANCEL),
            ]
        ]
    )


@router.message(Command("broadcast"))
@inject
async def start_broadcast(
    message: Message, state: FSMContext, config: FromDishka[AppConfig]
) -> None:
    if message.from_user is None or not is_admin(
        message.from_user.id, config.bot.admin_user_ids
    ):
        return
    await state.clear()
    await state.set_state(Broadcast.text)
    await message.answer(
        "📣 Жаппай хабарлама. Мәтінді жібер (немесе /cancel).\n"
        "Хабарлама жазылымнан бас тартпаған барлық қолданушыға жіберіледі."
    )


@router.message(Broadcast.text, F.text)
async def collect_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        return
    await state.update_data(text=text)
    await state.set_state(Broadcast.confirm)
    await message.answer(
        f"Осыны жіберейік пе?\n\n{text}", reply_markup=_confirm_keyboard()
    )


@router.callback_query(Broadcast.confirm, F.data == _SEND)
@inject
async def send_broadcast(
    callback: CallbackQuery,
    state: FSMContext,
    broadcast: FromDishka[BroadcastService],
) -> None:
    data = await state.get_data()
    await state.clear()
    await callback.answer()
    queued = await broadcast.broadcast_custom(str(data.get("text", "")))
    if isinstance(callback.message, Message):
        await callback.message.answer(f"✅ {queued} қолданушыға кезекке қойылды.")


@router.callback_query(Broadcast.confirm, F.data == _CANCEL)
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Болдырылмады")
    if isinstance(callback.message, Message):
        await callback.message.answer("❌ Болдырылмады.")
