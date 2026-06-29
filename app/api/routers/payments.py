"""Оплата: список тарифов, старт оплаты, загрузка чека Kaspi."""

from __future__ import annotations

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.deps.auth import get_current_user
from app.api.schemas.payment import PaymentInitIn, PaymentInitOut
from app.api.schemas.tariff import TariffOut
from app.application.services.payment_service import PaymentService
from app.application.services.subscription_service import SubscriptionService
from app.domain.entities.user import User
from app.domain.tariffs.catalog import all_tariffs

router = APIRouter(prefix="/api/payments", tags=["payments"], route_class=DishkaRoute)


@router.get("/tariffs", response_model=list[TariffOut])
async def list_tariffs() -> list[TariffOut]:
    return [TariffOut.from_domain(tariff) for tariff in all_tariffs()]


@router.post("/initiate", response_model=PaymentInitOut)
async def initiate_payment(
    body: PaymentInitIn,
    payments: FromDishka[PaymentService],
    user: User = Depends(get_current_user),
) -> PaymentInitOut:
    instruction = await payments.initiate(
        user_id=user.telegram_id, tariff_slug=body.tariff, method=body.method
    )
    return PaymentInitOut.from_domain(instruction)


@router.post("/proof")
async def submit_proof(
    subscription: FromDishka[SubscriptionService],
    user: User = Depends(get_current_user),
    tariff: str = Form(...),
    file: UploadFile = File(...),
) -> dict[str, str]:
    # PLAN (Фаза 7, Kaspi): залить файл чека боту → file_id → создать PaymentRequest(PENDING),
    # юзера → PENDING_REVIEW, переслать чек админам с кнопками ✅/❌. Активация — только после
    # одобрения, через SubscriptionService.activate (см. moderation.py).
    raise NotImplementedError
