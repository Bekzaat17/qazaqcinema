"""Оплата: список тарифов, старт оплаты, загрузка чека Kaspi."""

from __future__ import annotations

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit
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

_MAX_PROOF_BYTES = 10 * 1024 * 1024  # чек — картинка/PDF; крупнее 10 МБ не ждём

# Rate-limit (данные): платёжные write-ручки тяжёлые (создание инвойса / загрузка чека
# + уведомление админов) → лимитируем строже каталога. Легальному юзеру этого с запасом.
_initiate_rate_limited = Depends(rate_limit(limit=20, window_seconds=60, scope="pay_initiate"))
_proof_rate_limited = Depends(rate_limit(limit=15, window_seconds=300, scope="pay_proof"))


@router.get("/tariffs", response_model=list[TariffOut])
async def list_tariffs() -> list[TariffOut]:
    return [TariffOut.from_domain(tariff) for tariff in all_tariffs()]


@router.post("/initiate", response_model=PaymentInitOut, dependencies=[_initiate_rate_limited])
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


@router.post("/proof", response_model=ProofAccepted, dependencies=[_proof_rate_limited])
async def submit_proof(
    payments: FromDishka[PaymentService],
    user: User = Depends(get_current_user),
    tariff: str = Form(...),
    file: UploadFile = File(...),
) -> ProofAccepted:
    """Приём чека Kaspi: файл → PaymentRequest(PENDING) → модерация ✅/❌.

    Чек — картинка (скриншот) ИЛИ PDF (Kaspi отдаёт чек файлом). Видео/активацией не
    занимается: только регистрирует заявку и уводит юзера в `PENDING_REVIEW`. Подписку
    включит модератор (см. `PaymentModerationService`).
    """
    content_type = file.content_type or "application/octet-stream"
    if not (content_type.startswith("image/") or content_type == "application/pdf"):
        raise HTTPException(status_code=415, detail="image_or_pdf_expected")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty_file")
    if len(data) > _MAX_PROOF_BYTES:
        raise HTTPException(status_code=413, detail="file_too_large")
    default_name = "proof.pdf" if content_type == "application/pdf" else "proof.jpg"
    try:
        request = await payments.submit_proof(
            user,
            tariff,
            data,
            filename=file.filename or default_name,
            content_type=content_type,
        )
    except UnknownTariffError:
        raise HTTPException(status_code=400, detail="unknown_tariff") from None
    assert request.id is not None
    return ProofAccepted(request_id=request.id)
