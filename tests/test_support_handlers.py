"""Проверка прав админа и состояния диалога при ответе через бота."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from app.application.ports.telegram import TelegramTemporarilyUnavailableError
from app.bot.handlers import support

_CONFIG = SimpleNamespace(bot=SimpleNamespace(admin_user_ids=[77]))


def _message(user_id: int = 77) -> MagicMock:
    return MagicMock(
        spec=Message,
        from_user=SimpleNamespace(id=user_id),
        chat=SimpleNamespace(type="private"),
        text="Тексеріңіз, қолжетімділік ашық.",
        answer=AsyncMock(),
    )


async def test_non_admin_cannot_start_reply_or_grant_access() -> None:
    callback = SimpleNamespace(from_user=SimpleNamespace(id=88), answer=AsyncMock())
    state = AsyncMock(spec=FSMContext)
    access = AsyncMock()
    # Проверяем хендлеры без DI-обёртки: провайдеры собираются отдельно в build_dispatcher.
    await support.start_reply.__dishka_orig_func__(callback, state, _CONFIG)
    await support.grant_access.__dishka_orig_func__(callback, access, _CONFIG)
    state.clear.assert_not_awaited()
    access.grant.assert_not_awaited()
    assert callback.answer.await_count == 2


async def test_reply_button_sets_the_exact_recipient() -> None:
    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=77), answer=AsyncMock(),
        message=_message(), data="support:reply:8889467653",
    )
    state = AsyncMock(spec=FSMContext)
    await support.start_reply.__dishka_orig_func__(callback, state, _CONFIG)
    state.update_data.assert_awaited_once_with(reply_user_id=8889467653)
    state.set_state.assert_awaited_once_with(support.SupportReply.text)


async def test_reply_rechecks_admin_rights_before_sending() -> None:
    state = AsyncMock(spec=FSMContext)
    service = AsyncMock()
    await support.send_reply.__dishka_orig_func__(_message(88), state, service, _CONFIG)
    service.reply.assert_not_awaited()
    state.clear.assert_awaited_once()


async def test_reply_clears_state_only_after_delivery() -> None:
    state = AsyncMock(spec=FSMContext)
    state.get_data.return_value = {"reply_user_id": 8889467653}
    service = AsyncMock()
    message = _message()
    await support.send_reply.__dishka_orig_func__(message, state, service, _CONFIG)
    service.reply.assert_awaited_once_with(8889467653, message.text)
    state.clear.assert_awaited_once()
    assert "✅" in message.answer.call_args.args[0]


async def test_network_failure_keeps_recipient_and_never_reports_success() -> None:
    state = AsyncMock(spec=FSMContext)
    state.get_data.return_value = {"reply_user_id": 8889467653}
    service = AsyncMock()
    service.reply.side_effect = TelegramTemporarilyUnavailableError("network")
    message = _message()
    await support.send_reply.__dishka_orig_func__(message, state, service, _CONFIG)
    state.clear.assert_not_awaited()
    assert "✅" not in message.answer.call_args.args[0]
