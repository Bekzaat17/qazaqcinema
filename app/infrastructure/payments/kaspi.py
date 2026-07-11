"""Kaspi — ручная оплата: показываем реквизиты, юзер грузит скриншот чека.

Два способа перевода независимы и включаются ЗАПОЛНЕННОСТЬЮ env («данные», не код):
PAY_KASPI_NUMBER → перевод по номеру, PAY_KASPI_LINK → оплата по ссылке (Kaspi Pay).
Пустой параметр → `None` → способ скрыт на пэйволле (см. web `Paywall`). Заданы оба —
доступны оба; задан один — только он. Переключать способы = править env, без кода.
"""

from __future__ import annotations

from app.application.ports.payments import PaymentInstruction
from app.domain.entities.enums import PaymentMethod
from app.domain.tariffs.tariff import Tariff


class KaspiManualProvider:
    method = PaymentMethod.KASPI

    def __init__(self, kaspi_number: str, kaspi_name: str, kaspi_link: str = "") -> None:
        self._number = kaspi_number
        self._name = kaspi_name
        self._link = kaspi_link

    async def initiate(self, user_id: int, tariff: Tariff) -> PaymentInstruction:
        return PaymentInstruction(
            method=PaymentMethod.KASPI,
            # `or None`: пустой env-параметр → соответствующий способ скрыт на фронте.
            kaspi_number=self._number or None,
            kaspi_name=self._name or None,
            kaspi_link=self._link or None,
            payload=f"{user_id}:{tariff.slug}",
        )
