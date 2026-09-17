"""Ответ на личное сообщение мимо Mini App: кому он уходит и что в нём написано.

Роутер-фолбэк опасен ровно одним — перехватить чужое. Поэтому проверяем не только текст,
но и обе границы: личка (в группе обсуждений свои хендлеры) и пустой FSM (иначе бот
отвечал бы шаблоном на шаги визарда `/add`).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aiogram.types import Chat, Message
from app.bot.handlers import fallback
from app.bot.setup import build_dispatcher
from dishka import make_async_container

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


def _message(chat_type: str) -> Message:
    return Message(
        message_id=1, date=NOW, chat=Chat(id=1 if chat_type == "private" else -100, type=chat_type)
    )


def test_receipt_and_plain_message_get_different_openings() -> None:
    """Чек и вопрос — разные ситуации: «чек не туда» и «здесь вас не прочитают»."""
    receipt = fallback.hint_text(has_attachment=True)
    plain = fallback.hint_text(has_attachment=False)

    assert receipt.splitlines()[0] == plain.splitlines()[0] == "Сәлем! 😊"
    assert "Чекті осы чатқа жібердіңіз" in receipt and "жібердіңіз" not in plain
    assert "әкімшілер көрмейді" in plain and "әкімшілер көрмейді" not in receipt


@pytest.mark.parametrize("has_attachment", [True, False])
def test_both_roads_lead_into_the_mini_app(has_attachment: bool) -> None:
    """Обе дороги — внутри Mini App, и подписи те же, что человек видит на экране."""
    text = fallback.hint_text(has_attachment=has_attachment)

    for label in ("«Жазылу»", "«Kaspi арқылы төлеу»", "«Чекті жүктеу»"):
        assert label in text, label
    assert "«Қолдау қызметіне жазу»" in text
    assert "10–15 минут" in text


async def _passes(chat_type: str, raw_state: str | None) -> bool:
    """Пропускают ли фолбэк фильтры роутера. `check_root_filters` отдаёт (прошло, kwargs)."""
    passed, _ = await fallback.router.message.check_root_filters(
        _message(chat_type), raw_state=raw_state
    )
    return passed


async def test_answers_in_private_only_and_never_inside_a_wizard() -> None:
    assert await _passes("private", raw_state=None)
    # Шаг визарда `/add` (у админа активен FSM) фолбэк не трогает.
    assert not await _passes("private", raw_state="AddMovie:year")
    # Группа обсуждений: там отвечает `handlers/quiz`, а не шаблон про чек.
    assert not await _passes("supergroup", raw_state=None)


def test_fallback_is_the_last_router() -> None:
    """Порядок — часть решения: выше фолбэка стоят все, кто разбирает сообщение по делу."""
    routers = [router.name for router in build_dispatcher(make_async_container()).sub_routers]
    assert routers[-1] == "fallback"
    assert "start" in routers[:-1] and "add_movie" in routers[:-1]
