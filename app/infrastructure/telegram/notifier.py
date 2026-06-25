"""Адаптер исходящих уведомлений поверх aiogram Bot (реализует TelegramNotifier)."""

from __future__ import annotations

from aiogram import Bot


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

    async def send_payment_proof_to_admins(
        self,
        request_id: int,
        user_id: int,
        username: str | None,
        tariff_title: str,
        proof_file_id: str,
    ) -> None:
        # PLAN (фаза «оплата»): bot.send_photo(admin_chat_id, proof_file_id, caption=...,
        # reply_markup=moderation_keyboard(request_id)) — кнопки ✅ approve / ❌ reject.
        raise NotImplementedError
