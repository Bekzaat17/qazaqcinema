"""Выданное подписчику видео-сообщение (ссылка для последующего удаления).

Видео уходит в личку с `protect_content`, но файл всё равно оседает в чате на время
подписки. Чтобы «оплатил → скачал → пользуюсь вечно» не работало, каждую выдачу
запоминаем (chat_id + message_id) и удаляем эти сообщения, когда подписка истекает
(`SubscriptionService.expire_due`). Хранит ровно то, что нужно боту для `deleteMessage`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VideoDelivery:
    chat_id: int
    message_id: int
