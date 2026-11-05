"""Обращение в поддержку из Mini App: сообщение юзера уходит админам в личку.

Хранилища у обращения намеренно НЕТ: это не бизнес-сущность (ни статуса, ни жизненного
цикла, ни денег — в отличие от `payment_requests`), а сообщение. Переписка живёт там,
где ей место — в Telegram: админ отвечает автору через кнопку в карточке обращения.
Появится потребность в тикетах со статусами — тогда и появится таблица.

Сервис зависит только от порта `TelegramNotifier` (DIP): про aiogram не знает.
"""

from __future__ import annotations

from html import escape

from app.application.ports.telegram import TelegramNotifier
from app.domain.entities.user import User
from app.domain.errors import AppError
from app.domain.mention import mention_html

# Сколько символов сообщения доносим до админа (данные). Лимит подписи Telegram — 4096
# на сообщение; берём с запасом под шапку с реквизитами отправителя.
MAX_MESSAGE_LEN = 2000
_REPLY_HEADER = "💬 Қолдау қызметінің жауабы:\n\n"
MAX_REPLY_LEN = 4096 - len(_REPLY_HEADER.encode("utf-16-le")) // 2


class EmptySupportMessageError(AppError):
    """Пустое (или из одних пробелов) сообщение — отправлять нечего."""


class SupportReplyTooLongError(AppError):
    """Ответ вместе с заголовком превышает лимит сообщения Telegram."""


class SupportService:
    def __init__(self, notifier: TelegramNotifier) -> None:
        self._notifier = notifier

    async def reply(self, user_id: int, text: str) -> None:
        """Отправить ответ поддержки в чат пользователя с ботом."""
        message = text.strip()
        if not message:
            raise EmptySupportMessageError
        # Telegram считает длину в единицах UTF-16: эмодзи могут занимать две.
        if len(message.encode("utf-16-le")) // 2 > MAX_REPLY_LEN:
            raise SupportReplyTooLongError
        await self._notifier.notify_user(user_id, f"{_REPLY_HEADER}{message}")

    async def submit(self, user: User, text: str) -> None:
        """Переслать обращение всем админам.

        Недоставку не глотаем: `notify_admins` бросит `AdminsUnreachableError`, если
        не дошло ни до кого — пусть юзер узнает правду, а не увидит ложное «отправлено».
        """
        message = text.strip()
        if not message:
            raise EmptySupportMessageError
        await self._notifier.notify_admins(
            self._format(user, message[:MAX_MESSAGE_LEN]),
            user_id=user.telegram_id,
            username=user.username,
        )

    @staticmethod
    def _format(user: User, message: str) -> str:
        """Карточка обращения: кто написал (для ответа) + текст, отделённый чертой.

        Формат — тот же, что у карточки чека (`send_payment_proof_to_admins`): хэндл
        ссылкой (`mention_html`), в один тап открывающей чат с автором. Разметка HTML,
        поэтому текст юзера экранируем — иначе `<` в сообщении сломал бы парсинг и
        обращение вовсе не дошло бы.
        """
        return (
            "🆘 Қолдау сұрауы\n"
            f"Пайдаланушы: {mention_html(user.telegram_id, user.username)} "
            f"(id {user.telegram_id})\n"
            f"Статус: {user.status.value}\n"
            "———\n"
            f"{escape(message)}"
        )
