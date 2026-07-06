"""Юнит-тест доставки в worker'е рассылок (Фаза 12): успех + пропуск заблокировавших.

`_deliver` не должен пробрасывать ошибки Telegram (иначе «мёртвый» получатель зациклит
очередь): заблокировавшего бота помечаем `notifications_enabled=False`, прочее — логируем.
"""

from __future__ import annotations

from types import TracebackType

import pytest
from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from app.application.ports.broadcast import BroadcastJob, BroadcastMessage
from app.worker import _deliver


async def _nosleep(*_a: object, **_k: object) -> None:
    return None  # заменяет asyncio.sleep в тестах повтора — без реальной паузы


class _FakeUsers:
    def __init__(self) -> None:
        self.toggles: list[tuple[int, bool]] = []

    async def set_notifications(self, telegram_id: int, enabled: bool) -> None:
        self.toggles.append((telegram_id, enabled))


class _FakeRequestContainer:
    def __init__(self, users: _FakeUsers) -> None:
        self._users = users

    async def get(self, _: object) -> _FakeUsers:
        return self._users


class _FakeContainer:
    """Мимикрия под dishka: `container()` → async-контекст с `.get(UserRepository)`."""

    def __init__(self, users: _FakeUsers) -> None:
        self._users = users

    def __call__(self) -> _FakeContainer:
        return self

    async def __aenter__(self) -> _FakeRequestContainer:
        return _FakeRequestContainer(self._users)

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        return False


class _FakeNotifier:
    """Кидает по одному исключению из `errors` на каждую попытку, затем шлёт успешно."""

    def __init__(self, errors: list[BaseException] | None = None) -> None:
        self.sent: list[int] = []
        self._errors = list(errors or [])

    async def send_broadcast(self, chat_id: int, message: BroadcastMessage) -> None:
        if self._errors:
            raise self._errors.pop(0)
        self.sent.append(chat_id)


_JOB = BroadcastJob(chat_id=55, message=BroadcastMessage(text="x"), receipt="r")


async def test_deliver_sends_successfully() -> None:
    notifier = _FakeNotifier()
    users = _FakeUsers()
    await _deliver(_JOB, notifier, _FakeContainer(users))  # type: ignore[arg-type]
    assert notifier.sent == [55]
    assert users.toggles == []  # доставлено → флаг не трогаем


async def test_deliver_marks_blocked_user_off() -> None:
    forbidden = TelegramForbiddenError(
        method=None,  # type: ignore[arg-type]
        message="Forbidden: bot was blocked by the user",
    )
    notifier = _FakeNotifier([forbidden])
    users = _FakeUsers()
    await _deliver(_JOB, notifier, _FakeContainer(users))  # type: ignore[arg-type]
    assert notifier.sent == []                 # не доставлено
    assert users.toggles == [(55, False)]      # заблокировавший снят с рассылок


async def test_deliver_retries_transient_error_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.worker.asyncio.sleep", _nosleep)  # без реальной паузы
    notifier = _FakeNotifier(
        [TelegramNetworkError(method=None, message="net down")]  # type: ignore[arg-type]
    )
    users = _FakeUsers()
    await _deliver(_JOB, notifier, _FakeContainer(users))  # type: ignore[arg-type]
    assert notifier.sent == [55]  # краткий сетевой сбой → повтор удался (сообщение не потеряно)
    assert users.toggles == []    # получателя не блокируем


async def test_deliver_retry_after_then_forbidden_disables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.worker.asyncio.sleep", _nosleep)
    errors: list[BaseException] = [
        TelegramRetryAfter(method=None, message="flood", retry_after=1),  # type: ignore[arg-type]
        TelegramForbiddenError(method=None, message="bot was blocked"),   # type: ignore[arg-type]
    ]
    notifier = _FakeNotifier(errors)
    users = _FakeUsers()
    await _deliver(_JOB, notifier, _FakeContainer(users))  # type: ignore[arg-type]
    assert notifier.sent == []             # так и не доставлено
    assert users.toggles == [(55, False)]  # Forbidden на ПОВТОРЕ всё равно снял с рассылок
