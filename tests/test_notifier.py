"""Юнит-тесты AiogramNotifier на фейковом Bot.

`send_broadcast` (Фаза 12): фото+кнопка / только текст / фолбэк на текст, когда Telegram
не смог забрать постер по URL (TelegramBadRequest).
`notify_admins`: доставка каждому независимо — заблокировавший бота админ не должен
лишать остальных уведомления; ошибка только когда не дошло ни до кого.
"""

from __future__ import annotations

from typing import Any

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from app.application.ports.broadcast import BroadcastMessage
from app.application.ports.telegram import AdminsUnreachableError
from app.infrastructure.telegram.notifier import AiogramNotifier


class _FakeBot:
    def __init__(self, photo_fails: bool = False, blocked_chats: set[int] | None = None) -> None:
        self.photo_calls: list[dict[str, Any]] = []
        self.message_calls: list[dict[str, Any]] = []
        self._photo_fails = photo_fails
        self._blocked = blocked_chats or set()

    async def send_photo(
        self, chat_id: int, photo: str, caption: str | None = None, reply_markup: Any = None
    ) -> object:
        self.photo_calls.append({"caption": caption, "markup": reply_markup})
        if self._photo_fails:
            raise TelegramBadRequest(
                method=None,  # type: ignore[arg-type]
                message="Bad Request: failed to get HTTP URL content",
            )
        return object()

    async def send_message(self, chat_id: int, text: str, reply_markup: Any = None) -> object:
        if chat_id in self._blocked:
            raise TelegramForbiddenError(
                method=None,  # type: ignore[arg-type]
                message="Forbidden: bot was blocked by the user",
            )
        self.message_calls.append({"chat_id": chat_id, "text": text, "markup": reply_markup})
        return object()


def _notifier(bot: _FakeBot) -> AiogramNotifier:
    return AiogramNotifier(bot, admin_chat_id=0, admin_user_ids=[])  # type: ignore[arg-type]


async def test_send_broadcast_photo_with_button() -> None:
    bot = _FakeBot()
    message = BroadcastMessage(
        text="Жаңа", photo_url="https://x/p.jpg", button_text="Көру", button_url="https://x"
    )
    await _notifier(bot).send_broadcast(100, message)
    assert bot.photo_calls[0]["caption"] == "Жаңа"
    assert bot.photo_calls[0]["markup"] is not None  # inline-кнопка построена
    assert bot.message_calls == []                    # текстом не дублируем


async def test_send_broadcast_text_only_when_no_photo() -> None:
    bot = _FakeBot()
    await _notifier(bot).send_broadcast(100, BroadcastMessage(text="Тек мәтін"))
    assert bot.photo_calls == []
    assert bot.message_calls[0]["text"] == "Тек мәтін"
    assert bot.message_calls[0]["markup"] is None     # без кнопки


async def test_send_broadcast_falls_back_to_text_when_photo_unfetchable() -> None:
    bot = _FakeBot(photo_fails=True)
    message = BroadcastMessage(
        text="Жаңа фильм", photo_url="https://x/p.jpg", button_text="Көру", button_url="https://x"
    )
    await _notifier(bot).send_broadcast(100, message)
    assert len(bot.photo_calls) == 1                   # попытались фото
    assert bot.message_calls[0]["text"] == "Жаңа фильм"  # упало → текстом
    assert bot.message_calls[0]["markup"] is not None  # кнопка сохранена в фолбэке


# --- notify_admins: независимая доставка ---------------------------------

async def test_notify_admins_skips_blocked_and_reaches_the_rest() -> None:
    bot = _FakeBot(blocked_chats={1})
    notifier = AiogramNotifier(bot, admin_chat_id=0, admin_user_ids=[1, 2])  # type: ignore[arg-type]

    await notifier.notify_admins("сәлем")

    assert [call["chat_id"] for call in bot.message_calls] == [2]  # 1 заблокировал — не срываем


async def test_notify_admins_raises_when_nobody_got_it() -> None:
    bot = _FakeBot(blocked_chats={1, 2})
    notifier = AiogramNotifier(bot, admin_chat_id=0, admin_user_ids=[1, 2])  # type: ignore[arg-type]

    with pytest.raises(AdminsUnreachableError):
        await notifier.notify_admins("сәлем")
