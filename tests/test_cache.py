"""Юнит-тесты Redis-адаптеров кэша (Фаза 11): лок и rate-limiter.

Реальная логика (SET NX, фиксированное окно INCR/EXPIRE) — на in-memory fakeredis;
деградация (fail-open при недоступном Redis) — на стабе, который кидает RedisError.
"""

from __future__ import annotations

import fakeredis.aioredis
from app.infrastructure.cache.catalog import RedisCatalogCache
from app.infrastructure.cache.lock import RedisLock
from app.infrastructure.cache.rate_limiter import RedisRateLimiter
from app.infrastructure.cache.session import RedisSessionStore
from redis.exceptions import RedisError


def _redis() -> fakeredis.aioredis.FakeRedis:
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


class _BrokenRedis:
    """Redis, который всегда падает — для проверки fail-open адаптеров."""

    async def set(self, *args: object, **kwargs: object) -> object:
        raise RedisError("redis down")

    async def get(self, *args: object, **kwargs: object) -> object:
        raise RedisError("redis down")

    async def delete(self, *args: object, **kwargs: object) -> object:
        raise RedisError("redis down")

    def scan_iter(self, *args: object, **kwargs: object) -> object:
        raise RedisError("redis down")

    def pipeline(self, *args: object, **kwargs: object) -> object:
        raise RedisError("redis down")


# --- Lock (11.4) ----------------------------------------------------------

async def test_lock_acquire_then_blocked_same_key() -> None:
    lock = RedisLock(_redis())
    assert await lock.acquire("send_video:1:7", ttl_seconds=3) is True
    assert await lock.acquire("send_video:1:7", ttl_seconds=3) is False


async def test_lock_different_keys_independent() -> None:
    lock = RedisLock(_redis())
    assert await lock.acquire("send_video:1:7", ttl_seconds=3) is True
    assert await lock.acquire("send_video:1:8", ttl_seconds=3) is True


async def test_lock_fails_open_when_redis_down() -> None:
    lock = RedisLock(_BrokenRedis())
    assert await lock.acquire("send_video:1:7", ttl_seconds=3) is True


# --- RateLimiter (11.3) ---------------------------------------------------

async def test_rate_limiter_allows_up_to_limit_then_blocks() -> None:
    limiter = RedisRateLimiter(_redis())
    results = [await limiter.hit("catalog:1.2.3.4", limit=3, window_seconds=60) for _ in range(4)]
    assert results == [True, True, True, False]  # 4-е обращение за окно — сверх лимита


async def test_rate_limiter_keys_have_independent_windows() -> None:
    limiter = RedisRateLimiter(_redis())
    assert await limiter.hit("catalog:a", limit=1, window_seconds=60) is True
    assert await limiter.hit("catalog:a", limit=1, window_seconds=60) is False  # ключ a исчерпан
    assert await limiter.hit("catalog:b", limit=1, window_seconds=60) is True   # ключ b независим


async def test_rate_limiter_fails_open_when_redis_down() -> None:
    limiter = RedisRateLimiter(_BrokenRedis())
    assert await limiter.hit("catalog:1.2.3.4", limit=1, window_seconds=60) is True


# --- SessionStore (11.1) --------------------------------------------------

async def test_session_create_then_get_roundtrip() -> None:
    store = RedisSessionStore(_redis())
    token = await store.create(42, "beka")
    assert token is not None
    session = await store.get(token)
    assert session is not None
    assert session.user_id == 42
    assert session.username == "beka"


async def test_session_get_unknown_token_is_none() -> None:
    store = RedisSessionStore(_redis())
    assert await store.get("no-such-token") is None


async def test_session_fails_open_when_redis_down() -> None:
    store = RedisSessionStore(_BrokenRedis())
    assert await store.create(1, "x") is None       # не смогли завести → None (клиент на initData)
    assert await store.get("whatever") is None       # не смогли прочитать → None (→ 401 → ре-auth)


# --- CatalogCache (11.2) --------------------------------------------------

async def test_catalog_cache_set_get_invalidate() -> None:
    cache = RedisCatalogCache(_redis())
    assert await cache.get("home") is None                      # пусто на старте
    await cache.set("home", '{"shelves":[]}', 600)
    await cache.set("browse:all:year:desc:1:24", "[]", 60)      # другой ключ того же namespace
    assert await cache.get("home") == '{"shelves":[]}'           # хит
    await cache.invalidate()
    assert await cache.get("home") is None                      # invalidate чистит ВЕСЬ namespace
    assert await cache.get("browse:all:year:desc:1:24") is None


async def test_catalog_cache_fails_open_when_redis_down() -> None:
    cache = RedisCatalogCache(_BrokenRedis())
    assert await cache.get("home") is None                      # промах → эндпоинт соберёт из БД
    await cache.set("home", '{"shelves":[]}', 600)              # no-op, не бросает
    await cache.invalidate()                                     # no-op, не бросает
