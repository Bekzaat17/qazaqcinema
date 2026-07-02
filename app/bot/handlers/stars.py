"""Платёжные апдейты Telegram Stars: pre_checkout → successful_payment.

Тонкая презентация: `pre_checkout_query` нужно ответить в ~10 c, поэтому лишь быстро
валидируем payload (тариф существует) и подтверждаем. Реальный грант — на
`successful_payment` через `StarsPaymentService.confirm` (он же обрабатывает авто-продление).
"""

from __future__ import annotations

from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.types import Message, PreCheckoutQuery
from dishka import FromDishka
from dishka.integrations.aiogram import inject

from app.application.services.stars_service import StarsPaymentService

router = Router(name="stars")


@router.pre_checkout_query()
@inject
async def pre_checkout(
    query: PreCheckoutQuery, stars: FromDishka[StarsPaymentService]
) -> None:
    if stars.resolve_tariff(query.invoice_payload) is not None:
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Тариф табылмады. Кейінірек қайталаңыз.")


@router.message(F.successful_payment)
@inject
async def on_successful_payment(
    message: Message, stars: FromDishka[StarsPaymentService]
) -> None:
    payment = message.successful_payment
    if payment is None or message.from_user is None:
        return
    # confirm → activate() сам шлёт юзеру DM «жазылым белсендірілді»; отдельный ответ не нужен.
    await stars.confirm(
        payer_id=message.from_user.id,
        payload=payment.invoice_payload,
        charge_id=payment.telegram_payment_charge_id,
        now=datetime.now(UTC),
    )
