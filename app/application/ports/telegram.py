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

    async def acknowledge_payment_proof(
        self, telegram_id: int, proof: bytes, caption: str
    ) -> str:
        """Отправить пользователю его чек как подтверждение приёма; вернуть telegram file_id.

        Двойная роль: даёт юзеру обратную связь «чек получен» и одновременно — так как
        Telegram на любой upload возвращает file_id — отдаёт стабильный bot-owned
        `file_id`, который вызывающий переиспользует для пересылки чека админам.
        """
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
