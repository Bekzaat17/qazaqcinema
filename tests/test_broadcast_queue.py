"""Юнит-тесты RedisBroadcastQueue (Фаза 12) — надёжная очередь рассылок.

Реальная логика (RPUSH → LMOVE в processing → LREM ack → recover) — на fakeredis;
деградация (fail-open при недоступном Redis) — на стабе, кидающем RedisError.
"""

from __future__ import annotations

import fakeredis.aioredis
from app.application.ports.broadcast import BroadcastJob, BroadcastMessage
from app.infrastructure.cache.broadcast import RedisBroadcastQueue
from redis.exceptions import RedisError


def _redis() -> fakeredis.aioredis.FakeRedis:
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


class _BrokenRedis:
    """Redis, который всегда падает — для проверки fail-open очереди."""

    async def get(self, *a: object, **k: object) -> object:
        raise RedisError("down")

    async def lmove(self, *a: object, **k: object) -> object:
        raise RedisError("down")

    async def lrem(self, *a: object, **k: object) -> object:
        raise RedisError("down")

    def pipeline(self, *a: object, **k: object) -> object:
        raise RedisError("down")


_MSG = BroadcastMessage(
    text="Жаңа фильм", photo_url="https://x/p.jpg", button_text="Көру", button_url="https://x"
)


async def test_enqueue_reserve_roundtrip_preserves_message() -> None:
    queue = RedisBroadcastQueue(_redis())
    assert await queue.enqueue(_MSG, [1, 2, 3]) == 3
    jobs = await queue.reserve(10)
    assert [job.chat_id for job in jobs] == [1, 2, 3]  # FIFO
    assert jobs[0].message == _MSG                      # payload восстановлен целиком


async def test_reserve_resolves_shared_payload_once() -> None:
    """Получатели одной рассылки делят payload → reserve резолвит его ОДИН раз (одна и та
    же инстанция BroadcastMessage на все задания), а не делает GET на каждого получателя."""
    queue = RedisBroadcastQueue(_redis())
    await queue.enqueue(_MSG, [1, 2, 3])
    jobs = await queue.reserve(10)
    assert jobs[0].message == _MSG
    assert jobs[0].message is jobs[1].message is jobs[2].message  # разрешён единожды


async def test_reserve_respects_batch() -> None:
    queue = RedisBroadcastQueue(_redis())
    await queue.enqueue(_MSG, [1, 2, 3, 4, 5])
    assert [job.chat_id for job in await queue.reserve(2)] == [1, 2]
    assert [job.chat_id for job in await queue.reserve(2)] == [3, 4]


async def test_ack_removes_and_recover_returns_only_unacked() -> None:
    queue = RedisBroadcastQueue(_redis())
    await queue.enqueue(_MSG, [1, 2])
    jobs = await queue.reserve(2)
    await queue.ack(jobs[0])                 # первый доставлен и подтверждён
    # второй остался «в работе» (worker упал до ack) → recover вернёт его в очередь
    assert await queue.recover() == 1
    assert [job.chat_id for job in await queue.reserve(2)] == [2]


async def test_reserve_empty_queue_returns_empty() -> None:
    assert await RedisBroadcastQueue(_redis()).reserve(5) == []


async def test_enqueue_empty_recipients_is_noop() -> None:
    assert await RedisBroadcastQueue(_redis()).enqueue(_MSG, []) == 0


async def test_reserve_drops_job_when_payload_expired() -> None:
    redis = _redis()
    queue = RedisBroadcastQueue(redis)
    await queue.enqueue(_MSG, [1])
    async for key in redis.scan_iter("broadcast:msg:*"):  # эмулируем протухший TTL payload
        await redis.delete(key)
    assert await queue.reserve(5) == []  # неотправимое задание снято, не отдано


async def test_queue_fails_open_when_redis_down() -> None:
    queue = RedisBroadcastQueue(_BrokenRedis())
    assert await queue.enqueue(_MSG, [1, 2]) == 0   # рассылка пропущена, вызывающий не падает
    assert await queue.reserve(5) == []
    await queue.ack(BroadcastJob(1, _MSG, "receipt"))  # no-op, не бросает
    assert await queue.recover() == 0
