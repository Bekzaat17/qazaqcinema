"""Адаптер исходящих уведомлений поверх aiogram Bot (реализует TelegramNotifier)."""

from __future__ import annotations

import contextlib

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)

from app.application.ports.broadcast import BroadcastMessage
from app.application.ports.telegram import ProofRef, RecipientUnreachableError

# Переиспользуем фабрику клавиатуры модерации, чтобы формат callback-data (pay:approve|
# reject:<id>) жил в одном месте — тут её пишем, в bot/handlers/moderation.py читаем.
from app.bot.keyboards.moderation import moderation_keyboard


def _broadcast_keyboard(message: BroadcastMessage) -> InlineKeyboardMarkup | None:
    """Inline-кнопка «Көру» (открывает Web App в личке). None — если кнопка не задана."""
    if not (message.button_text and message.button_url):
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=message.button_text, web_app=WebAppInfo(url=message.button_url)
                )
            ]
        ]
    )


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

    async def send_broadcast(self, chat_id: int, message: BroadcastMessage) -> None:
        keyboard = _broadcast_keyboard(message)
        if message.photo_url is not None:
            try:
                await self._bot.send_photo(
                    chat_id, message.photo_url, caption=message.text, reply_markup=keyboard
                )
                return
            except TelegramBadRequest:
                # Telegram не смог забрать постер по URL (или подпись длиннее лимита) →
                # шлём текстом, чтобы не потерять уведомление. RetryAfter/Forbidden сюда
                # не попадают (это отдельные классы) — их обрабатывает worker.
                pass
        await self._bot.send_message(chat_id, message.text, reply_markup=keyboard)

    async def send_protected_video(
        self, chat_id: int, file_id: str, caption: str | None = None
    ) -> int:
        # protect_content=True — ядро безопасности: получатель не может скачать/переслать.
        try:
            message = await self._bot.send_video(
                chat_id, file_id, caption=caption, protect_content=True
            )
        except TelegramForbiddenError as exc:
            # Юзер не открыл чат с ботом / заблокировал → понятный сигнал наверх, не 500.
            raise RecipientUnreachableError(str(exc)) from exc
        except TelegramBadRequest as exc:
            if "chat not found" in str(exc).lower():
                raise RecipientUnreachableError(str(exc)) from exc
            raise  # прочий BadRequest (напр. битый file_id) — настоящая ошибка, пусть всплывёт
        return message.message_id  # запоминаем выдачу → удалим при истечении подписки

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        # Best-effort: сообщение могло быть уже удалено, а юзер — заблокировать бота.
        # Удаление при истечении подписки не должно падать из-за одного «мёртвого» id.
        with contextlib.suppress(TelegramBadRequest, TelegramForbiddenError):
            await self._bot.delete_message(chat_id, message_id)

    async def acknowledge_payment_proof(
        self, telegram_id: int, proof: bytes, caption: str, *, filename: str, content_type: str
    ) -> ProofRef:
        # Отправляем чек обратно юзеру (подтверждение приёма); ответ Telegram содержит
        # file_id (bot-owned) — его переиспользуем для пересылки чека админам.
        # Картинку шлём как photo (инлайн-превью), PDF-чек Kaspi — как document.
        payload = BufferedInputFile(proof, filename)
        if content_type.startswith("image/"):
            message = await self._bot.send_photo(telegram_id, payload, caption=caption)
            if not message.photo:
                raise RuntimeError("Telegram did not return a photo file_id")
            return ProofRef(message.photo[-1].file_id, is_document=False)
        message = await self._bot.send_document(telegram_id, payload, caption=caption)
        if message.document is None:
            raise RuntimeError("Telegram did not return a document file_id")
        return ProofRef(message.document.file_id, is_document=True)

    async def send_payment_proof_to_admins(
        self,
        *,
        request_id: int,
        user_id: int,
        username: str | None,
        tariff_title: str,
        proof: ProofRef,
    ) -> None:
        handle = f"@{username}" if username else f"id{user_id}"
        # «Чек №N» — первой строкой и крупно (номер = request_id, тот же в кнопках ниже):
        # админ сверяет чек с его кнопками по номеру, не путается в стопке заявок.
        caption = (
            f"🧾 Чек №{request_id}\n"
            f"Пайдаланушы: {handle} (id {user_id})\n"
            f"Тариф: {tariff_title}"
        )
        keyboard = moderation_keyboard(request_id)
        # Тем же способом, что приняли: PDF → document, картинка → photo (file_id'ы разнотипны).
        if proof.is_document:
            await self._bot.send_document(
                self._admin_chat_id, proof.file_id, caption=caption, reply_markup=keyboard
            )
        else:
            await self._bot.send_photo(
                self._admin_chat_id, proof.file_id, caption=caption, reply_markup=keyboard
            )
