from __future__ import annotations

import asyncio

import fakeredis.aioredis
import pytest
from app.infrastructure.cache.boardgame import RedisRoomEvents


async def test_late_publisher_does_not_hide_a_newer_room_revision() -> None:
    async with fakeredis.aioredis.FakeRedis(decode_responses=True) as redis:
        events = RedisRoomEvents(redis)
        await events.publish("ROOM", 5)
        await events.publish("ROOM", 4)
        assert await redis.get("board:revision:ROOM") == "5"
        # Подписчик прочитал версию 4 до изменения: ждать следующего хода не нужно.
        await asyncio.wait_for(events.wait("ROOM", 4, 25), timeout=1)


async def test_concurrent_publishers_keep_the_highest_committed_revision() -> None:
    async with fakeredis.aioredis.FakeRedis(decode_responses=True) as redis:
        events = RedisRoomEvents(redis)
        await asyncio.gather(*(events.publish("ROOM", revision) for revision in (7, 2, 9, 3, 8)))
        assert await redis.get("board:revision:ROOM") == "9"


async def test_waiter_observes_an_update_published_during_subscription() -> None:
    async with fakeredis.aioredis.FakeRedis(decode_responses=True) as redis:
        events = RedisRoomEvents(redis)
        await events.publish("ROOM", 4)
        waiting = asyncio.create_task(events.wait("ROOM", 4, 25))
        try:
            await events.publish("ROOM", 5)
            await asyncio.wait_for(waiting, timeout=1)
        finally:
            waiting.cancel()
            await asyncio.gather(waiting, return_exceptions=True)


async def test_redis_failure_is_logged_without_breaking_the_game(
    caplog: pytest.LogCaptureFixture,
) -> None:
    server = fakeredis.FakeServer()
    server.connected = False
    async with fakeredis.aioredis.FakeRedis(server=server, decode_responses=True) as redis:
        await RedisRoomEvents(redis).publish("ROOM", 5)
    assert "Сигнал обновления комнаты не доставлен" in caplog.text
