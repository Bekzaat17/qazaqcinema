"""Redis-адаптер порта `RateLimiter` — фиксированное окно на `INCR`/`EXPIRE`.

Namespace-префикс `ratelimit:` — здесь. Атомарность окна: `SET key 0 EX window NX`
(создаёт счётчик с TTL только при ПЕРВОМ обращении окна) + `INCR` в одном пайплайне.
TTL выставляется ровно один раз на окно и самоочищается — при падении между
командами ключ живёт не дольше окна (нет «залипшего» счётчика без TTL, который
навсегда заблокировал бы клиента).

**Fail-open:** Redis недоступен → пропускаем (лучше обслужить, чем ошибочно вернуть
429 всем). Заметка: фиксированное окно допускает всплеск до 2×limit на стыке двух
окон — для MVP приемлемо; при необходимости точности → скользящее окно.
"""

from __future__ import annotations

import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.application.ports.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

_PREFIX = "ratelimit:"


class RedisRateLimiter(RateLimiter):
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        full = f"{_PREFIX}{key}"
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.set(full, 0, ex=window_seconds, nx=True)
                pipe.incr(full)
                _, count = await pipe.execute()
        except RedisError:
            logger.warning("Redis rate limiter unavailable, failing open", exc_info=True)
            return True
        return int(count) <= limit
