"""Юнит-тесты AiogramNotifier на фейковом Bot.

`send_broadcast`: постер ФАЙЛОМ С ДИСКА + кнопка / только текст / фолбэк на текст, если
файла нет или Telegram отказал на самом фото (TelegramBadRequest).
`notify_admins`: доставка каждому независимо — заблокировавший бота админ не должен
лишать остальных уведомления; ошибка только когда не дошло ни до кого.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from app.application.ports.broadcast import BroadcastMessage
from app.application.ports.telegram import AdminsUnreachableError, ProofRef
from app.infrastructure.telegram.notifier import AiogramNotifier


class _FakeBot:
    def __init__(self, photo_fails: bool = False, blocked_chats: set[int] | None = None) -> None:
        self.photo_calls: list[dict[str, Any]] = []
        self.document_calls: list[dict[str, Any]] = []
        self.message_calls: list[dict[str, Any]] = []
        self._photo_fails = photo_fails
        self._blocked = blocked_chats or set()

    async def send_photo(
        self,
        chat_id: int,
        photo: Any,
        caption: str | None = None,
        parse_mode: str | None = None,
        reply_markup: Any = None,
    ) -> object:
        if chat_id in self._blocked:
            raise TelegramForbiddenError(
                method=None,  # type: ignore[arg-type]
                message="Forbidden: bot was blocked by the user",
            )
        self.photo_calls.append(
            {"chat_id": chat_id, "photo": photo, "caption": caption,
             "parse_mode": parse_mode, "markup": reply_markup}
        )
        if self._photo_fails:
            raise TelegramBadRequest(
                method=None,  # type: ignore[arg-type]
                message="Bad Request: failed to get HTTP URL content",
            )
        return object()

    async def send_document(
        self,
        chat_id: int,
        document: str,
        caption: str | None = None,
        parse_mode: str | None = None,
        reply_markup: Any = None,
    ) -> object:
        if chat_id in self._blocked:
            raise TelegramForbiddenError(
                method=None,  # type: ignore[arg-type]
                message="Forbidden: bot was blocked by the user",
            )
        self.document_calls.append(
            {"chat_id": chat_id, "caption": caption, "parse_mode": parse_mode,
             "markup": reply_markup}
        )
        return object()

    async def send_message(
        self, chat_id: int, text: str, parse_mode: str | None = None, reply_markup: Any = None
    ) -> object:
        if chat_id in self._blocked:
            raise TelegramForbiddenError(
                method=None,  # type: ignore[arg-type]
                message="Forbidden: bot was blocked by the user",
            )
        self.message_calls.append(
            {"chat_id": chat_id, "text": text, "parse_mode": parse_mode, "markup": reply_markup}
        )
        return object()


def _notifier(
    bot: _FakeBot,
    *,
    admin_chat_id: int = 0,
    admin_user_ids: list[int] | None = None,
    media_root: str = "uploads",
) -> AiogramNotifier:
    """Нотификатор на фейковом Bot — одна фабрика на файл, чтобы новый параметр
    адаптера не переписывал десяток тестов."""
    return AiogramNotifier(  # type: ignore[arg-type]
        bot, admin_chat_id, admin_user_ids or [], media_root
    )


def _media_root_with_poster(tmp_path: Path) -> str:
    """Медиа-корень, в котором постер РЕАЛЬНО лежит: файла нет → уйдёт текстом."""
    poster = tmp_path / "posters" / "p.jpg"
    poster.parent.mkdir(parents=True)
    poster.write_bytes(b"jpeg")
    return str(tmp_path)


def _message(photo_path: str | None = "posters/p.jpg") -> BroadcastMessage:
    return BroadcastMessage(
        text="Жаңа фильм", photo_path=photo_path, button_text="Көру", button_url="https://x"
    )


async def test_send_broadcast_sends_the_poster_as_a_file_not_a_url(tmp_path: Path) -> None:
    """Постер уходит файлом с диска: по ссылке Telegram его не скачает (хостер режет
    входящий трафик с диапазонов Telegram, тот же повод, что у `BOT_FORCE_POLLING`)."""
    bot = _FakeBot()
    notifier = _notifier(bot, media_root=_media_root_with_poster(tmp_path))
    await notifier.send_broadcast(100, _message())
    assert bot.photo_calls[0]["photo"].path == tmp_path / "posters" / "p.jpg"
    assert bot.photo_calls[0]["caption"] == "Жаңа фильм"
    assert bot.photo_calls[0]["markup"] is not None  # inline-кнопка построена
    assert bot.message_calls == []                    # текстом не дублируем


async def test_send_broadcast_text_only_when_no_photo() -> None:
    bot = _FakeBot()
    await _notifier(bot).send_broadcast(100, BroadcastMessage(text="Тек мәтін"))
    assert bot.photo_calls == []
    assert bot.message_calls[0]["text"] == "Тек мәтін"
    assert bot.message_calls[0]["markup"] is None     # без кнопки


async def test_send_broadcast_goes_out_as_text_when_the_poster_file_is_missing(
    tmp_path: Path,
) -> None:
    """Том `uploads` не смонтирован воркеру → письмо уходит текстом, а не теряется."""
    bot = _FakeBot()
    await _notifier(bot, media_root=str(tmp_path)).send_broadcast(100, _message())
    assert bot.photo_calls == []
    assert bot.message_calls[0]["text"] == "Жаңа фильм"
    assert bot.message_calls[0]["markup"] is not None  # кнопка сохранена


async def test_send_broadcast_falls_back_to_text_when_telegram_rejects_the_photo(
    tmp_path: Path,
) -> None:
    bot = _FakeBot(photo_fails=True)
    notifier = _notifier(bot, media_root=_media_root_with_poster(tmp_path))
    await notifier.send_broadcast(100, _message())
    assert len(bot.photo_calls) == 1                   # попытались фото
    assert bot.message_calls[0]["text"] == "Жаңа фильм"  # упало → текстом
    assert bot.message_calls[0]["markup"] is not None  # кнопка сохранена в фолбэке


# --- notify_admins: независимая доставка ---------------------------------

async def test_notify_admins_skips_blocked_and_reaches_the_rest() -> None:
    bot = _FakeBot(blocked_chats={1})
    notifier = _notifier(bot, admin_chat_id=0, admin_user_ids=[1, 2])

    await notifier.notify_admins("сәлем")

    assert [call["chat_id"] for call in bot.message_calls] == [2]  # 1 заблокировал — не срываем


async def test_notify_admins_raises_when_nobody_got_it() -> None:
    bot = _FakeBot(blocked_chats={1, 2})
    notifier = _notifier(bot, admin_chat_id=0, admin_user_ids=[1, 2])

    with pytest.raises(AdminsUnreachableError):
        await notifier.notify_admins("сәлем")


async def test_notify_admins_sends_html() -> None:
    """Карточки админа содержат ссылку-хэндл → уходят как HTML (см. domain/mention.py)."""
    bot = _FakeBot()
    notifier = _notifier(bot, admin_chat_id=0, admin_user_ids=[1])

    await notifier.notify_admins("сәлем")

    assert bot.message_calls[0]["parse_mode"] == "HTML"


# --- карточка чека: хэндл ссылкой ----------------------------------------

async def test_payment_proof_caption_links_the_handle() -> None:
    bot = _FakeBot()
    notifier = _notifier(bot, admin_chat_id=99, admin_user_ids=[])

    await notifier.send_payment_proof_to_admins(
        request_id=5,
        user_id=42,
        username="beka",
        tariff_title="1 ай",
        proof=ProofRef("file-1", is_document=False),
    )

    (call,) = bot.photo_calls
    assert '<a href="https://t.me/beka">@beka</a>' in call["caption"]
    assert call["parse_mode"] == "HTML"
    assert call["markup"] is not None  # кнопки ✅/❌ на месте


async def test_payment_proof_document_keeps_link_for_user_without_username() -> None:
    bot = _FakeBot()
    notifier = _notifier(bot, admin_chat_id=99, admin_user_ids=[])

    await notifier.send_payment_proof_to_admins(
        request_id=5,
        user_id=42,
        username=None,
        tariff_title="1 ай",
        proof=ProofRef("file-1", is_document=True),
    )

    (call,) = bot.document_calls
    assert '<a href="tg://user?id=42">id 42</a>' in call["caption"]
    assert call["parse_mode"] == "HTML"


# --- карточка чека: копия каждому админу ----------------------------------


async def _send_proof(notifier: AiogramNotifier, *, is_document: bool = False) -> None:
    await notifier.send_payment_proof_to_admins(
        request_id=7,
        user_id=42,
        username="beka",
        tariff_title="1 ай",
        proof=ProofRef("file-1", is_document=is_document),
    )


async def test_payment_proof_goes_to_every_admin() -> None:
    bot = _FakeBot()
    notifier = _notifier(bot, admin_chat_id=0, admin_user_ids=[1, 2])

    await _send_proof(notifier)

    assert [call["chat_id"] for call in bot.photo_calls] == [1, 2]
    assert all(call["markup"] is not None for call in bot.photo_calls)


async def test_payment_proof_is_not_duplicated_for_the_moderation_chat() -> None:
    """Прод-конфиг: `BOT_ADMIN_CHAT_ID` — личка админа, он же в `BOT_ADMIN_USER_IDS`."""
    bot = _FakeBot()
    notifier = _notifier(bot, admin_chat_id=1, admin_user_ids=[1, 2])

    await _send_proof(notifier)

    assert [call["chat_id"] for call in bot.photo_calls] == [1, 2]


async def test_payment_proof_document_goes_to_every_admin() -> None:
    bot = _FakeBot()
    notifier = _notifier(bot, admin_chat_id=99, admin_user_ids=[1])

    await _send_proof(notifier, is_document=True)

    assert [call["chat_id"] for call in bot.document_calls] == [99, 1]


async def test_payment_proof_skips_blocked_admin_and_reaches_the_rest() -> None:
    bot = _FakeBot(blocked_chats={1})
    notifier = _notifier(bot, admin_chat_id=0, admin_user_ids=[1, 2])

    await _send_proof(notifier)

    assert [call["chat_id"] for call in bot.photo_calls] == [2]


async def test_payment_proof_raises_when_nobody_got_it() -> None:
    bot = _FakeBot(blocked_chats={1, 2})
    notifier = _notifier(bot, admin_chat_id=0, admin_user_ids=[1, 2])

    with pytest.raises(AdminsUnreachableError):
        await _send_proof(notifier)
