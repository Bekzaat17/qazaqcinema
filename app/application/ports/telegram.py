"""Порт исходящих действий в Telegram, нужных доменным сервисам.

Реализуется адаптером поверх aiogram Bot (app/infrastructure/telegram). Выдача
inline-видео живёт в самом bot-хендлере (InlineQueryResultCachedVideo) и сюда не
входит — здесь только то, что инициируют сервисы (DM, пересылка чека админам).
"""

from __future__ import annotations

from typing import Protocol


class TelegramNotifier(Protocol):
    async def notify_user(self, telegram_id: int, text: str) -> None: ...

    async def notify_admins(self, text: str) -> None: ...

    async def send_payment_proof_to_admins(
        self,
        request_id: int,
        user_id: int,
        username: str | None,
        tariff_title: str,
        proof_file_id: str,
    ) -> None:
        """Переслать скриншот чека в чат модерации с кнопками ✅ / ❌."""
        ...
