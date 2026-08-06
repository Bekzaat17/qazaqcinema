"""Юнит-тесты обращений в поддержку: что уходит админам и когда мы отказываем."""

from __future__ import annotations

import pytest
from app.application.ports.telegram import AdminsUnreachableError
from app.application.services.support_service import (
    MAX_MESSAGE_LEN,
    EmptySupportMessageError,
    SupportService,
)
from app.domain.entities.enums import UserStatus
from app.domain.entities.user import User


class _FakeNotifier:
    def __init__(self, *, unreachable: bool = False) -> None:
        self.messages: list[str] = []
        self._unreachable = unreachable

    async def notify_admins(self, text: str) -> None:
        if self._unreachable:
            raise AdminsUnreachableError("никто не получил")
        self.messages.append(text)


async def test_submit_sends_card_with_handle_and_text() -> None:
    notifier = _FakeNotifier()
    user = User(telegram_id=42, username="aibek", status=UserStatus.ACTIVE)

    await SupportService(notifier).submit(user, "  Видео келмей жатыр  ")

    (sent,) = notifier.messages
    assert "@aibek" in sent          # хэндл — чтобы админ ответил в один тап
    assert "id 42" in sent
    assert "active" in sent
    assert "Видео келмей жатыр" in sent  # текст обрезан по краям, но не изменён


async def test_submit_falls_back_to_id_without_username() -> None:
    notifier = _FakeNotifier()

    await SupportService(notifier).submit(User(telegram_id=7), "сұрақ бар")

    assert "id 7" in notifier.messages[0]


async def test_submit_rejects_blank_message() -> None:
    notifier = _FakeNotifier()

    with pytest.raises(EmptySupportMessageError):
        await SupportService(notifier).submit(User(telegram_id=1), "   \n  ")

    assert notifier.messages == []


async def test_submit_truncates_overlong_message() -> None:
    notifier = _FakeNotifier()

    await SupportService(notifier).submit(User(telegram_id=1), "я" * (MAX_MESSAGE_LEN + 500))

    assert notifier.messages[0].count("я") == MAX_MESSAGE_LEN


async def test_submit_propagates_undelivered() -> None:
    """Не дошло ни до кого → ошибка наверх: юзеру нельзя говорить «отправлено»."""
    with pytest.raises(AdminsUnreachableError):
        await SupportService(_FakeNotifier(unreachable=True)).submit(User(telegram_id=1), "сәлем")
