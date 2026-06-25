"""Оплата: список тарифов, старт оплаты, загрузка чека Kaspi."""

from __future__ import annotations

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, File, Form, UploadFile

from app.api.schemas.payment import PaymentInitIn, PaymentInitOut
from app.api.schemas.tariff import TariffOut
from app.application.services.payment_service import PaymentService
from app.application.services.subscription_service import SubscriptionService
from app.domain.tariffs.catalog import all_tariffs

router = APIRouter(prefix="/api/payments", tags=["payments"], route_class=DishkaRoute)


@router.get("/tariffs", response_model=list[TariffOut])
async def list_tariffs() -> list[TariffOut]:
    return [TariffOut.from_domain(tariff) for tariff in all_tariffs()]


@router.post("/initiate", response_model=PaymentInitOut)
async def initiate_payment(
    body: PaymentInitIn, payments: FromDishka[PaymentService]
) -> PaymentInitOut:
    # user_id будет извлекаться из initData на фазе авторизации (PLAN).
    instruction = await payments.initiate(user_id=0, tariff_slug=body.tariff, method=body.method)
    return PaymentInitOut.from_domain(instruction)


@router.post("/proof")
async def submit_proof(
    subscription: FromDishka[SubscriptionService],
    tariff: str = Form(...),
    file: UploadFile = File(...),
) -> dict[str, str]:
    # PLAN (оплата): валидировать юзера (initData) → залить файл боту/в канал → file_id →
    # SubscriptionService.submit_proof(...). Пока — скелет.
    raise NotImplementedError
