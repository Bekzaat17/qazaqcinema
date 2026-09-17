"""Гейт недельного выбора: кто считается подписчиком канала и что кэшируется.

Два решения проверяются здесь именно тестом, потому что оба «неочевидно правильные»:
fail-open при сбое Telegram и кэш ТОЛЬКО положительного ответа.
"""

from __future__ import annotations

from typing import Any

import pytest
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
from app.infrastructure.cache.membership import CachedChannelMembership
from app.infrastructure.telegram.channel import AiogramChannelMembership
from redis.exceptions import RedisError

CHANNEL_ID = -1001234567890


class _Member:
    """Ответ `getChatMember`: адаптер смотрит только статус и `is_member`."""

    def __init__(self, status: str, is_member: bool = False) -> None:
        self.status = status
        self.is_member = is_member


class _FakeBot:
    def __init__(self, answer: _Member | Exception) -> None:
        self._answer = answer
        self.calls: list[tuple[int, int]] = []

    async def get_chat_member(self, chat_id: int, user_id: int) -> Any:
        self.calls.append((chat_id, user_id))
        if isinstance(self._answer, Exception):
            raise self._answer
        return self._answer


def _adapter(answer: _Member | Exception, channel_id: int = CHANNEL_ID) -> tuple[Any, _FakeBot]:
    bot = _FakeBot(answer)
    return AiogramChannelMembership(bot, channel_id), bot  # type: ignore[arg-type]


# ── Кто считается подписчиком ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "status",
    [ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER],
)
async def test_present_statuses_count_as_subscribed(status: str) -> None:
    membership, _ = _adapter(_Member(status))
    assert await membership.is_member(42)


@pytest.mark.parametrize("status", [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED])
async def test_absent_statuses_do_not(status: str) -> None:
    membership, _ = _adapter(_Member(status))
    assert not await membership.is_member(42)


async def test_restricted_is_decided_by_is_member_not_by_status() -> None:
    """`restricted` — единственный статус, где имени мало: человек может быть и в канале
    (ограничен в правах), и уже вышедшим."""
    inside, _ = _adapter(_Member(ChatMemberStatus.RESTRICTED, is_member=True))
    outside, _ = _adapter(_Member(ChatMemberStatus.RESTRICTED, is_member=False))

    assert await inside.is_member(42)
    assert not await outside.is_member(42)


# ── Деградация ───────────────────────────────────────────────────────────────


async def test_channel_not_configured_lets_everyone_through() -> None:
    """dev и тесты живут без канала и ничего не отключают руками."""
    membership, bot = _adapter(_Member(ChatMemberStatus.LEFT), channel_id=0)

    assert await membership.is_member(42)
    assert bot.calls == []  # Telegram даже не спрашивали


async def test_telegram_failure_fails_open() -> None:
    """Отказать подписчику дороже, чем пустить чужого: сбой ≠ «не подписан».

    Сюда же попадает потерянная у бота админка в канале — всплеск бесплатных выдач
    виден в дневном отчёте, а люди при этом не упираются в стену.
    """
    membership, _ = _adapter(TelegramAPIError(method=None, message="boom"))  # type: ignore[arg-type]
    assert await membership.is_member(42)


# ── Кэш ──────────────────────────────────────────────────────────────────────


class _FakeRedis:
    def __init__(self, broken: bool = False) -> None:
        self.store: dict[str, Any] = {}
        self.broken = broken

    async def get(self, key: str) -> Any:
        if self.broken:
            raise RedisError("down")
        return self.store.get(key)

    async def set(self, key: str, value: Any, ex: int | None = None) -> None:
        if self.broken:
            raise RedisError("down")
        self.store[key] = value


class _CountingInner:
    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.calls = 0

    async def is_member(self, user_id: int) -> bool:
        self.calls += 1
        return self.answer


async def test_yes_is_cached_and_no_is_not() -> None:
    """Человек уходит подписываться и жмёт «Тексеру»: закэшируй мы отказ — он бы его и
    увидел, уже будучи подписчиком."""
    yes, no = _CountingInner(True), _CountingInner(False)
    redis = _FakeRedis()

    for _ in range(3):
        assert await CachedChannelMembership(yes, redis).is_member(42)  # type: ignore[arg-type]
    for _ in range(3):
        assert not await CachedChannelMembership(no, redis).is_member(7)  # type: ignore[arg-type]

    assert yes.calls == 1   # спросили Telegram один раз
    assert no.calls == 3    # отказ не кэшируется


async def test_broken_redis_still_answers_from_telegram() -> None:
    """Кэш не имеет права быть точкой отказа: падает и `get`, и `set`."""
    inner = _CountingInner(True)
    cached = CachedChannelMembership(inner, _FakeRedis(broken=True))  # type: ignore[arg-type]

    assert await cached.is_member(42)
    assert inner.calls == 1
