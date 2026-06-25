"""Kaspi — ручная оплата: показываем реквизиты, юзер грузит скриншот чека."""

from __future__ import annotations

from app.application.ports.payments import PaymentInstruction
from app.domain.entities.enums import PaymentMethod
from app.domain.tariffs.tariff import Tariff


class KaspiManualProvider:
    method = PaymentMethod.KASPI

    def __init__(self, kaspi_number: str, kaspi_name: str) -> None:
        self._number = kaspi_number
        self._name = kaspi_name

    async def initiate(self, user_id: int, tariff: Tariff) -> PaymentInstruction:
        return PaymentInstruction(
            method=PaymentMethod.KASPI,
            kaspi_number=self._number,
            kaspi_name=self._name,
            payload=f"{user_id}:{tariff.slug}",
        )
