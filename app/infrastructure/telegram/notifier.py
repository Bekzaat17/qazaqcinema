"""Адаптер исходящих уведомлений поверх aiogram Bot (реализует TelegramNotifier)."""

from __future__ import annotations

import asyncio
import logging
from html import escape

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)

from app.application.ports.broadcast import BroadcastMessage
from app.application.ports.telegram import (
    AdminsUnreachableError,
    DeleteOutcome,
    ProofRef,
    RecipientUnreachableError,
)

# Переиспользуем фабрику клавиатуры модерации, чтобы формат callback-data (pay:approve|
# reject:<id>) жил в одном месте — тут её пишем, в bot/handlers/moderation.py читаем.
from app.bot.keyboards.moderation import moderation_keyboard
from app.domain.mention import mention_html

logger = logging.getLogger(__name__)


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

    def _admin_recipients(self) -> list[int]:
        """Кому уходит карточка чека: чат модерации + личка КАЖДОГО админа, без повторов.

        Дедупликация обязательна: в проде `BOT_ADMIN_CHAT_ID` — это личка одного из
        админов, то есть он же есть и в `BOT_ADMIN_USER_IDS`; без сверки он получал бы
        два одинаковых чека с двумя парами кнопок. Порядок сохраняем (чат модерации
        первым) — так номера чеков в основном чате идут ровной лентой.
        """
        recipients: list[int] = []
        for chat_id in (self._admin_chat_id, *self._admin_user_ids):
            # 0 — «чат модерации не задан» (дефолт конфига, .env.test): не адресат.
            if chat_id and chat_id not in recipients:
                recipients.append(chat_id)
        return recipients

    async def notify_admins(self, text: str) -> None:
        # Каждому админу — независимо: один заблокировавший бота не должен лишать
        # уведомления остальных (раньше первый же 403 обрывал цикл). Молчим, только
        # если не дошло ни до кого — тогда вызывающий вправе сказать это юзеру.
        delivered = 0
        for admin_id in self._admin_user_ids:
            try:
                # HTML — карточки админа содержат ссылку-хэндл (`domain/mention.py`);
                # подставляемые данные экранирует вызывающий (порт это оговаривает).
                await self._bot.send_message(admin_id, text, parse_mode="HTML")
                delivered += 1
            except TelegramAPIError:
                logger.warning("Не доставлено админу %s", admin_id, exc_info=True)
        if delivered == 0:
            raise AdminsUnreachableError(
                f"Ни один из {len(self._admin_user_ids)} админов не получил сообщение"
            )

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

    async def delete_message(self, chat_id: int, message_id: int) -> DeleteOutcome:
        """Удалить своё сообщение; классифицировать отказ (см. `DeleteOutcome`).

        Раньше отказ глушился `suppress` вчистую — провал был невидим: главный из них,
        «сообщение старше 48 часов», выглядел как успех. Теперь исход возвращаем наверх, а
        причину пишем в лог.

        Классификация — здесь, потому что это единственный слой, знающий aiogram:
          • BadRequest / Forbidden → REFUSED. Постоянно: >48 ч, сообщения уже нет, бот
            заблокирован. Ретраить нечего — вызывающий сносит строку.
          • RetryAfter → сначала пробуем переждать сами (пауза + повтор); не помогло → FAILED.
          • Network / 5xx → FAILED. Раньше НЕ ловились вовсе и роняли весь джоб чистки.
        """
        for attempt in (1, 2):
            try:
                await self._bot.delete_message(chat_id, message_id)
                return DeleteOutcome.DELETED
            except TelegramRetryAfter as exc:
                if attempt == 2:
                    logger.warning("Повторный флуд-лимит на удалении в чате %s", chat_id)
                    return DeleteOutcome.FAILED
                await asyncio.sleep(exc.retry_after + 1)
            except (TelegramBadRequest, TelegramForbiddenError) as exc:
                logger.warning(
                    "Отказ удаления сообщения %s в чате %s (не повторяем): %s",
                    message_id,
                    chat_id,
                    exc,
                )
                return DeleteOutcome.REFUSED
            except (TelegramNetworkError, TelegramServerError) as exc:
                logger.warning(
                    "Временный сбой удаления %s в чате %s (повторим позже): %s",
                    message_id,
                    chat_id,
                    exc,
                )
                return DeleteOutcome.FAILED
        return DeleteOutcome.FAILED

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
        # «Чек №N» — первой строкой и крупно (номер = request_id, тот же в кнопках ниже):
        # админ сверяет чек с его кнопками по номеру, не путается в стопке заявок.
        # Хэндл — ссылкой (HTML), чтобы написать автору чека в один тап; тариф наш, но
        # экранируем и его — подпись целиком идёт как HTML.
        caption = (
            f"🧾 Чек №{request_id}\n"
            f"Пайдаланушы: {mention_html(user_id, username)} (id {user_id})\n"
            f"Тариф: {escape(tariff_title)}"
        )
        keyboard = moderation_keyboard(request_id)
        # Копия — каждому админу, доставка независимая (как в `notify_admins`): админ, не
        # нажавший /start или заблокировавший бота, не должен оставить остальных без чека.
        # Одобрение идемпотентно (`PaymentModerationService` отдаёт ALREADY_HANDLED), так
        # что несколько живых копий с кнопками подписку дважды не выдадут.
        delivered = 0
        for chat_id in self._admin_recipients():
            try:
                # Тем же способом, что приняли: PDF → document, картинка → photo
                # (photo-file_id и document-file_id несовместимы).
                if proof.is_document:
                    await self._bot.send_document(
                        chat_id,
                        proof.file_id,
                        caption=caption,
                        parse_mode="HTML",
                        reply_markup=keyboard,
                    )
                else:
                    await self._bot.send_photo(
                        chat_id,
                        proof.file_id,
                        caption=caption,
                        parse_mode="HTML",
                        reply_markup=keyboard,
                    )
                delivered += 1
            except TelegramAPIError:
                logger.warning("Чек №%s не доставлен в чат %s", request_id, chat_id, exc_info=True)
        if delivered == 0:
            # Молчать нельзя: юзер уже получил «чек принят», а модерировать его некому.
            # Ошибка наверх → статус PENDING_REVIEW не проставится (см. `PaymentService`).
            raise AdminsUnreachableError(f"Чек №{request_id} не дошёл ни до одного админа")
