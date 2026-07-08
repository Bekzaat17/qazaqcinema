"""Порт исходящих действий в Telegram, нужных доменным сервисам.

Реализуется адаптером поверх aiogram Bot (app/infrastructure/telegram). Здесь только
то, что инициируют сервисы: DM, пересылка чека админам и защищённая выдача видео.
Inline-результаты НЕ умеют protect_content, поэтому видео отдаётся через
`send_protected_video` (прямой send_video), а не inline-хендлером.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.application.ports.broadcast import BroadcastMessage


@dataclass(frozen=True, slots=True)
class ProofRef:
    """Ссылка на принятый чек в Telegram: file_id + КАК его слать (фото/документ).

    Kaspi отдаёт чек и картинкой, и PDF: картинку шлём как photo (инлайн-превью),
    PDF — как document. Тип определяем один раз при приёме и несём дальше (в чат
    админов), т.к. photo-file_id и document-file_id несовместимы — повторная отправка
    должна идти тем же способом, что и первая.
    """

    file_id: str
    is_document: bool


class RecipientUnreachableError(Exception):
    """Получатель недоступен для бота (не открыл чат / заблокировал → «chat not found»).

    Бросает адаптер `send_protected_video`, ловит `PlaybackService` — чтобы отдать
    понятный ответ («откройте бота»), а не пробросить сырую ошибку Telegram в 500.
    """


class TelegramNotifier(Protocol):
    async def notify_user(self, telegram_id: int, text: str) -> None: ...

    async def notify_admins(self, text: str) -> None: ...

    async def send_broadcast(self, chat_id: int, message: BroadcastMessage) -> None:
        """Отправить одно сообщение рассылки (Фаза 12): фото+подпись или текст, опц. кнопка.

        Ошибки Telegram (RetryAfter/Forbidden) НЕ глушим — их обрабатывает worker
        (спит на RetryAfter, помечает заблокировавших). Глушим лишь падение отправки
        фото по URL → фолбэк на текст.
        """
        ...

    async def send_protected_video(
        self, chat_id: int, file_id: str, caption: str | None = None
    ) -> int:
        """Видео в личку с protect_content=True; вернуть message_id отправленного сообщения.

        message_id нужен, чтобы запомнить выдачу (`VideoDeliveryRepository`) и удалить её,
        когда подписка истечёт (иначе видео осталось бы в чате навсегда).
        """
        ...

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        """Удалить своё сообщение (best-effort). «Уже нет / заблокирован» — молча глотаем."""
        ...

    async def acknowledge_payment_proof(
        self, telegram_id: int, proof: bytes, caption: str, *, filename: str, content_type: str
    ) -> ProofRef:
        """Отправить пользователю его чек как подтверждение приёма; вернуть `ProofRef`.

        Двойная роль: даёт юзеру обратную связь «чек получен» и одновременно — так как
        Telegram на любой upload возвращает file_id — отдаёт стабильный bot-owned
        `file_id`, который вызывающий переиспользует для пересылки чека админам.
        `content_type`/`filename` — чтобы адаптер выбрал photo (картинка) или document
        (PDF-чек Kaspi) и вернул это в `ProofRef.is_document`.
        """
        ...

    async def send_payment_proof_to_admins(
        self,
        *,
        request_id: int,
        user_id: int,
        username: str | None,
        tariff_title: str,
        proof: ProofRef,
    ) -> None:
        """Переслать чек (фото или PDF-документ) в чат модерации с кнопками ✅ / ❌."""
        ...
