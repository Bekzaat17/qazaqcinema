"""Старт оплаты: по способу выбирает PaymentProvider (Strategy) и отдаёт инструкцию."""

from __future__ import annotations

from collections.abc import Mapping

from app.application.ports.payments import PaymentInstruction, PaymentProvider
from app.domain.entities.enums import PaymentMethod


class PaymentService:
    def __init__(self, providers: Mapping[PaymentMethod, PaymentProvider]) -> None:
        self._providers = providers

    async def initiate(
        self, user_id: int, tariff_slug: str, method: PaymentMethod
    ) -> PaymentInstruction:
        """Вернуть инструкцию по оплате (реквизиты Kaspi / ссылку инвойса Stars).

        Алгоритм:
          1. tariff = get_tariff(tariff_slug)  # None → ошибка валидации
          2. provider = self._providers[method]
          3. return await provider.initiate(user_id, tariff)
        """
        raise NotImplementedError
