"""Порт способа оплаты (Strategy).

Каждый способ (Kaspi/Stars/фиат) реализует `PaymentProvider.initiate`, возвращая
`PaymentInstruction` — что показать/сделать пользователю:
  • Kaspi  → реквизиты для перевода, дальше юзер грузит скриншот чека;
  • Stars  → ссылка/payload инвойса Telegram;
  • фиат   → ссылка инвойса провайдера.
Бизнес-логика подписки не знает деталей способа (Open/Closed, DIP).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.entities.enums import PaymentMethod
from app.domain.tariffs.tariff import Tariff


@dataclass(slots=True)
class PaymentInstruction:
    method: PaymentMethod
    # Kaspi: номер и ссылка независимы, показываются по заполненности (перевод по
    # номеру и/или оплата по ссылке) — какой env задан, тот способ и доступен.
    kaspi_number: str | None = None   # перевод по номеру (None → способ скрыт)
    kaspi_name: str | None = None     # имя получателя (показывается рядом с номером)
    kaspi_link: str | None = None     # Kaspi Pay-ссылка на оплату (None → способ скрыт)
    invoice_url: str | None = None    # Stars/фиат: ссылка на инвойс
    payload: str | None = None        # служебный payload для сопоставления платежа


class PaymentProvider(Protocol):
    method: PaymentMethod

    async def initiate(self, user_id: int, tariff: Tariff) -> PaymentInstruction: ...
