"""Redis-адаптер порта `Lock` — короткоживущий лок через `SET key val EX ttl NX`.

Namespace-префикс `lock:` — здесь (Redis-концерн). **Fail-open:** если Redis
недоступен, `acquire` возвращает True — недоступность координатора не должна
блокировать основной сценарий (лучше рискнуть повторной отправкой видео, чем не
отдать его вовсе). Деградация фиксируется на этом уровне, сервис про неё не знает.
"""

from __future__ import annotations

import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.application.ports.lock import Lock

logger = logging.getLogger(__name__)

_PREFIX = "lock:"


class RedisLock(Lock):
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def acquire(self, key: str, ttl_seconds: int) -> bool:
        try:
            # SET NX → True при установке, None если ключ уже есть (лок занят).
            acquired = await self._redis.set(f"{_PREFIX}{key}", "1", ex=ttl_seconds, nx=True)
        except RedisError:
            logger.warning("Redis lock unavailable, failing open", exc_info=True)
            return True
        return bool(acquired)
