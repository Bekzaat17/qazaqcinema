"""Оплата: список тарифов, старт оплаты, загрузка чека Kaspi."""

from __future__ import annotations

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.deps.auth import get_current_user
from app.api.schemas.payment import PaymentInitIn, PaymentInitOut, ProofAccepted
from app.api.schemas.tariff import TariffOut
from app.application.services.payment_service import (
    PaymentService,
    UnknownTariffError,
    UnsupportedMethodError,
)
from app.domain.entities.user import User
from app.domain.tariffs.catalog import all_tariffs

router = APIRouter(prefix="/api/payments", tags=["payments"], route_class=DishkaRoute)

_MAX_PROOF_BYTES = 10 * 1024 * 1024  # чек — картинка; крупнее 10 МБ не ждём


@router.get("/tariffs", response_model=list[TariffOut])
async def list_tariffs() -> list[TariffOut]:
    return [TariffOut.from_domain(tariff) for tariff in all_tariffs()]


@router.post("/initiate", response_model=PaymentInitOut)
async def initiate_payment(
    body: PaymentInitIn,
    payments: FromDishka[PaymentService],
    user: User = Depends(get_current_user),
) -> PaymentInitOut:
    try:
        instruction = await payments.initiate(
            user_id=user.telegram_id, tariff_slug=body.tariff, method=body.method
        )
    except UnknownTariffError:
        raise HTTPException(status_code=400, detail="unknown_tariff") from None
    except UnsupportedMethodError:
        raise HTTPException(status_code=400, detail="unsupported_method") from None
    return PaymentInitOut.from_domain(instruction)


@router.post("/proof", response_model=ProofAccepted)
async def submit_proof(
    payments: FromDishka[PaymentService],
    user: User = Depends(get_current_user),
    tariff: str = Form(...),
    file: UploadFile = File(...),
) -> ProofAccepted:
    """Приём чека Kaspi: файл → PaymentRequest(PENDING) → модерация ✅/❌.

    Видео/активацией не занимается: только регистрирует заявку и уводит юзера в
    `PENDING_REVIEW`. Подписку включит модератор (см. `PaymentModerationService`).
    """
    if file.content_type is not None and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="image_expected")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty_file")
    if len(data) > _MAX_PROOF_BYTES:
        raise HTTPException(status_code=413, detail="file_too_large")
    try:
        request = await payments.submit_proof(user, tariff, data)
    except UnknownTariffError:
        raise HTTPException(status_code=400, detail="unknown_tariff") from None
    assert request.id is not None
    return ProofAccepted(request_id=request.id)
