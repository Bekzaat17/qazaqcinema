"""DTO старта оплаты."""

from __future__ import annotations

from pydantic import BaseModel

from app.application.ports.payments import PaymentInstruction
from app.domain.entities.enums import PaymentMethod


class PaymentInitIn(BaseModel):
    tariff: str
    method: PaymentMethod = PaymentMethod.KASPI


class ProofAccepted(BaseModel):
    """Ответ на загрузку чека: что теперь со статусом человека.

    `status` — РЕАЛЬНОЕ состояние, а не константа: обычно чек открывает доступ сразу
    (`active`), но у того, кому уже трижды отказывали, заявка уходит админу
    (`pending_review`). Фронт по этому полю выбирает, что показать, — гадать по коду
    ответа он не должен.
    """

    status: str
    request_id: int


class PaymentInitOut(BaseModel):
    method: str
    kaspi_number: str | None = None
    kaspi_name: str | None = None
    kaspi_link: str | None = None
    invoice_url: str | None = None
    payload: str | None = None

    @classmethod
    def from_domain(cls, instruction: PaymentInstruction) -> PaymentInitOut:
        return cls(
            method=instruction.method.value,
            kaspi_number=instruction.kaspi_number,
            kaspi_name=instruction.kaspi_name,
            kaspi_link=instruction.kaspi_link,
            invoice_url=instruction.invoice_url,
            payload=instruction.payload,
        )
