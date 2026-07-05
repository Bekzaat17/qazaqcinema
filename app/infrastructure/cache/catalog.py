"""Redis-адаптер порта `CatalogCache` — cache-aside для главного экрана.

Один ключ `catalog:main` → JSON `{hero, movies}`, TTL 600 c (10 мин). **Fail-open:**
Redis недоступен → `get` → None (эндпоинт соберёт из БД), `set`/`invalidate` — тихий
no-op. Т.е. падение Redis лишь снимает ускорение, отдачу каталога не ломает.
"""

from __future__ import annotations

import logging
from typing import cast

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.application.ports.catalog_cache import CatalogCache

logger = logging.getLogger(__name__)

_KEY = "catalog:main"
_TTL_SECONDS = 600


class RedisCatalogCache(CatalogCache):
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get(self) -> str | None:
        try:
            # decode_responses=True → строка; стабы redis типизируют шире (bytes|str|None).
            return cast("str | None", await self._redis.get(_KEY))
        except RedisError:
            logger.warning("Redis catalog cache unavailable, failing open", exc_info=True)
            return None

    async def set(self, payload: str) -> None:
        try:
            await self._redis.set(_KEY, payload, ex=_TTL_SECONDS)
        except RedisError:
            logger.warning("Redis catalog cache unavailable, skipping set", exc_info=True)

    async def invalidate(self) -> None:
        try:
            await self._redis.delete(_KEY)
        except RedisError:
            logger.warning("Redis catalog cache unavailable, skipping invalidate", exc_info=True)
