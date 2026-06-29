"""Модерация чеков: кнопки ✅/❌ в админ-чате.

Скелет. Реализация — PLAN (Фаза 7, Kaspi):
  1. Разобрать callback_data 'pay:approve:<id>' / 'pay:reject:<id>'.
  2. approve → PaymentRequest=APPROVED + достать User → SubscriptionService.activate(user, tariff,
     now) (грант живёт в Фазе 6, не дублируем); reject → PaymentRequest=REJECTED.
  3. Обновить сообщение/ответить админу, уведомить юзера (DM шлёт activate / отдельный notify).
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

router = Router(name="moderation")


@router.callback_query(F.data.startswith("pay:"))
async def handle_moderation(callback: CallbackQuery) -> None:
    await callback.answer()  # TODO(PLAN: оплата): approve/reject через SubscriptionService
