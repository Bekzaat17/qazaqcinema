"""DTO старта оплаты."""

from __future__ import annotations

from pydantic import BaseModel

from app.application.ports.payments import PaymentInstruction
from app.domain.entities.enums import PaymentMethod


class PaymentInitIn(BaseModel):
    tariff: str
    method: PaymentMethod = PaymentMethod.KASPI


class ProofAccepted(BaseModel):
    """Ответ на загрузку чека: заявка принята и ушла на модерацию."""

    status: str = "pending_review"
    request_id: int


class PaymentInitOut(BaseModel):
    method: str
    kaspi_number: str | None = None
    kaspi_name: str | None = None
    invoice_url: str | None = None
    payload: str | None = None

    @classmethod
    def from_domain(cls, instruction: PaymentInstruction) -> PaymentInitOut:
        return cls(
            method=instruction.method.value,
            kaspi_number=instruction.kaspi_number,
            kaspi_name=instruction.kaspi_name,
            invoice_url=instruction.invoice_url,
            payload=instruction.payload,
        )
