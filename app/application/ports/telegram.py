"""Порт исходящих действий в Telegram, нужных доменным сервисам.

Реализуется адаптером поверх aiogram Bot (app/infrastructure/telegram). Здесь только
то, что инициируют сервисы: DM, пересылка чека админам и защищённая выдача видео.
Inline-результаты НЕ умеют protect_content, поэтому видео отдаётся через
`send_protected_video` (прямой send_video), а не inline-хендлером.
"""

from __future__ import annotations

from typing import Protocol


class TelegramNotifier(Protocol):
    async def notify_user(self, telegram_id: int, text: str) -> None: ...

    async def notify_admins(self, text: str) -> None: ...

    async def send_protected_video(
        self, chat_id: int, file_id: str, caption: str | None = None
    ) -> None:
        """Видео в личку с protect_content=True (запрет скачивания/пересылки/записи экрана)."""
        ...

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
