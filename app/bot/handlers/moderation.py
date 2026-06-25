"""Модерация чеков: кнопки ✅/❌ в админ-чате.

Скелет. Реализация — PLAN (фаза «оплата»):
  1. Разобрать callback_data 'pay:approve:<id>' / 'pay:reject:<id>'.
  2. approve → SubscriptionService.approve(request_id, now); reject → .reject(...).
  3. Обновить сообщение/ответить админу, уведомить юзера (внутри сервиса).
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

router = Router(name="moderation")


@router.callback_query(F.data.startswith("pay:"))
async def handle_moderation(callback: CallbackQuery) -> None:
    await callback.answer()  # TODO(PLAN: оплата): approve/reject через SubscriptionService
