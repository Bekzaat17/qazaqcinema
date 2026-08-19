"""Redis-адаптер порта `DailyPin` — закреп фильма дня на текущие сутки.

Namespace-префикс `daily:` — здесь (Redis-концерн), домен про него не знает.
**Fail-open:** Redis недоступен → `get` отдаёт None (работает обычная ротация), `set`
молча ничего не делает. Потерять закреп не страшно — это разовый жест админа, а вот
уронить из-за него главную было бы неприемлемо.

Хранение именно в Redis, а не в БД, намеренно: у записи нет ни истории, ни жизненного
цикла, ни аудита — она обязана исчезнуть в полночь сама. Колонка в `movies` под это
означала бы вечный флаг, который кто-то однажды забудет снять.
"""

from __future__ import annotations

import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.application.ports.daily_pin import DailyPin

logger = logging.getLogger(__name__)

_PREFIX = "daily:pin:"


class RedisDailyPin(DailyPin):
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get(self, day: int) -> int | None:
        try:
            raw = await self._redis.get(f"{_PREFIX}{day}")
        except RedisError:
            logger.warning("Redis daily pin unavailable, falling back to rotation", exc_info=True)
            return None
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            # Мусор в ключе не имеет права ломать главную — просто ротация.
            logger.warning("Битое значение закрепа фильма дня: %r", raw)
            return None

    async def set(self, day: int, movie_id: int, ttl_seconds: int) -> None:
        try:
            await self._redis.set(f"{_PREFIX}{day}", movie_id, ex=max(ttl_seconds, 1))
        except RedisError:
            logger.warning("Redis daily pin unavailable, pin skipped", exc_info=True)
