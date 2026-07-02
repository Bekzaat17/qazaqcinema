"""Адаптер исходящих уведомлений поверх aiogram Bot (реализует TelegramNotifier)."""

from __future__ import annotations

from aiogram import Bot
from aiogram.types import BufferedInputFile

# Переиспользуем фабрику клавиатуры модерации, чтобы формат callback-data (pay:approve|
# reject:<id>) жил в одном месте — тут её пишем, в bot/handlers/moderation.py читаем.
from app.bot.keyboards.moderation import moderation_keyboard


class AiogramNotifier:
    def __init__(self, bot: Bot, admin_chat_id: int, admin_user_ids: list[int]) -> None:
        self._bot = bot
        self._admin_chat_id = admin_chat_id
        self._admin_user_ids = admin_user_ids

    async def notify_user(self, telegram_id: int, text: str) -> None:
        await self._bot.send_message(telegram_id, text)

    async def notify_admins(self, text: str) -> None:
        for admin_id in self._admin_user_ids:
            await self._bot.send_message(admin_id, text)

    async def send_protected_video(
        self, chat_id: int, file_id: str, caption: str | None = None
    ) -> None:
        # protect_content=True — ядро безопасности: получатель не может скачать/переслать.
        await self._bot.send_video(
            chat_id, file_id, caption=caption, protect_content=True
        )

    async def acknowledge_payment_proof(
        self, telegram_id: int, proof: bytes, caption: str
    ) -> str:
        # Отправляем чек обратно юзеру (подтверждение приёма); ответ Telegram содержит
        # file_id (bot-owned) — его переиспользуем для пересылки чека админам.
        message = await self._bot.send_photo(
            telegram_id, BufferedInputFile(proof, "proof.jpg"), caption=caption
        )
        if not message.photo:
            raise RuntimeError("Telegram did not return a photo file_id")
        return message.photo[-1].file_id

    async def send_payment_proof_to_admins(
        self,
        request_id: int,
        user_id: int,
        username: str | None,
        tariff_title: str,
        proof_file_id: str,
    ) -> None:
        handle = f"@{username}" if username else f"id{user_id}"
        caption = (
            "🧾 Жаңа төлем чегі\n"
            f"Пайдаланушы: {handle} (id {user_id})\n"
            f"Тариф: {tariff_title}\n"
            f"Өтініш #{request_id}"
        )
        await self._bot.send_photo(
            self._admin_chat_id,
            proof_file_id,
            caption=caption,
            reply_markup=moderation_keyboard(request_id),
        )
