"""Личный ответ админа автору обращения через бота; адресат хранится в FSM."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from dishka import FromDishka
from dishka.integrations.aiogram import inject

from app.application.ports.telegram import (
    RecipientUnreachableError,
    TelegramTemporarilyUnavailableError,
)
from app.application.services.support_access_service import (
    SupportAccessOutcome,
    SupportAccessService,
)
from app.application.services.support_service import (
    EmptySupportMessageError,
    SupportReplyTooLongError,
    SupportService,
)
from app.bot.keyboards.contact import GRANT_PREFIX, REPLY_PREFIX
from app.bot.security import is_admin
from app.config.settings import AppConfig
from app.domain.catalog.daily import TZ

logger = logging.getLogger(__name__)
router = Router(name="support")


class SupportReply(StatesGroup):
    text = State()


@router.callback_query(F.data.startswith(GRANT_PREFIX))
@inject
async def grant_access(
    callback: CallbackQuery,
    access: FromDishka[SupportAccessService],
    config: FromDishka[AppConfig],
) -> None:
    if not is_admin(callback.from_user.id, config.bot.admin_user_ids):
        await callback.answer("Тек әкімші", show_alert=True)
        return
    parts = (callback.data or "").removeprefix(GRANT_PREFIX).split(":")
    if len(parts) != 2 or not parts[0].isdecimal() or int(parts[0]) <= 0:
        await callback.answer("Қате пайдаланушы", show_alert=True)
        return
    user_id = int(parts[0])
    await callback.answer("Өңделуде…")
    result = await access.grant(user_id, parts[1], datetime.now(UTC))
    messages = {
        SupportAccessOutcome.GRANTED: "✅ Қолжетімділік ашылды",
        SupportAccessOutcome.ALREADY_OPEN: "☑️ Қолжетімділік бұрыннан ашық — мерзім өзгермеді",
        SupportAccessOutcome.NOT_FOUND: "❌ Пайдаланушы табылмады",
        SupportAccessOutcome.UNKNOWN_TARIFF: "❌ Тариф табылмады",
        SupportAccessOutcome.GRANTED_UNNOTIFIED: (
            "✅ Қолжетімділік ашылды, бірақ хабарлама жеткізілмеді"
        ),
    }
    text = f"id {user_id}: {messages[result.outcome]}"
    if result.expires_at is not None:
        text += f"\n🕒 {result.expires_at.astimezone(TZ):%d.%m.%Y %H:%M} дейін (Алматы)."
    if isinstance(callback.message, Message):
        await callback.message.answer(text)


@router.callback_query(F.data.startswith(REPLY_PREFIX))
@inject
async def start_reply(
    callback: CallbackQuery, state: FSMContext, config: FromDishka[AppConfig]
) -> None:
    if not is_admin(callback.from_user.id, config.bot.admin_user_ids):
        await callback.answer("Тек әкімші", show_alert=True)
        return
    if not isinstance(callback.message, Message):
        await callback.answer("Хабарлама қолжетімсіз", show_alert=True)
        return
    if callback.message.chat.type != "private":
        await callback.answer(
            "Ботпен жеке чаттағы өтініш көшірмесін ашыңыз.", show_alert=True
        )
        return
    raw_id = (callback.data or "").removeprefix(REPLY_PREFIX)
    if not raw_id.isdecimal() or int(raw_id) <= 0:
        await callback.answer("Қате пайдаланушы", show_alert=True)
        return
    user_id = int(raw_id)
    await state.clear()
    await state.update_data(reply_user_id=user_id)
    await state.set_state(SupportReply.text)
    await callback.answer()
    await callback.message.answer(
        f"✉️ Жауап алушы: id {user_id}.\n"
        "Жауап мәтінін жіберіңіз — бот оны пайдаланушыға жеткізеді.\n"
        "/cancel — болдырмау."
    )


@router.message(SupportReply.text, F.chat.type == "private")
@inject
async def send_reply(
    message: Message,
    state: FSMContext,
    support: FromDishka[SupportService],
    config: FromDishka[AppConfig],
) -> None:
    # Права могли измениться после нажатия кнопки — проверяем и саму отправку.
    if message.from_user is None or not is_admin(
        message.from_user.id, config.bot.admin_user_ids
    ):
        await state.clear()
        return
    if (message.text or "").startswith("/"):
        await message.answer("Жауап мәтінін жіберіңіз немесе /cancel басыңыз.")
        return
    data = await state.get_data()
    user_id = data.get("reply_user_id")
    if not isinstance(user_id, int) or user_id <= 0:
        await state.clear()
        await message.answer("Алушы табылмады. Өтініштегі жауап батырмасын қайта басыңыз.")
        return
    try:
        await support.reply(user_id, message.text or "")
    except EmptySupportMessageError:
        await message.answer("Жауапты мәтін түрінде жіберіңіз немесе /cancel басыңыз.")
        return
    except SupportReplyTooLongError:
        await message.answer("Мәтін тым ұзын. Жауапты қысқартып, қайта жіберіңіз.")
        return
    except RecipientUnreachableError:
        await state.clear()
        await message.answer(
            "❌ Жеткізілмеді: пайдаланушы ботты бұғаттаған немесе ботпен чат ашпаған."
        )
        return
    except (TelegramTemporarilyUnavailableError, TelegramAPIError):
        logger.warning("Қолдау жауабы id %s пайдаланушыға жеткізілмеді", user_id, exc_info=True)
        await message.answer(
            "⚠️ Жеткізу расталмады. Кейінірек қайталап көріңіз немесе /cancel басыңыз."
        )
        return
    await state.clear()
    await message.answer(f"✅ Жауап id {user_id} пайдаланушыға жіберілді.")
