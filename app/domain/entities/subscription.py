"""Заявка на оплату — единая модель для всех способов (Kaspi/Stars/фиат).

Универсальна по способу оплаты: `proof_file_id` — для Kaspi (скриншот чека),
`external_charge_id` — для Stars/фиата (id платежа провайдера). Лишнее поле
просто остаётся None. Это даёт аудит модерации и историю оплат.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.entities.enums import PaymentMethod, PaymentStatus


@dataclass(slots=True)
class PaymentRequest:
    user_id: int
    tariff: str
    method: PaymentMethod
    status: PaymentStatus = PaymentStatus.PENDING
    proof_file_id: str | None = None        # Kaspi: telegram file_id скриншота чека
    external_charge_id: str | None = None   # Stars/фиат: id платежа провайдера
    created_at: datetime | None = None
    reviewed_at: datetime | None = None
    id: int | None = None
