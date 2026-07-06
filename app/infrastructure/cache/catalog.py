"""Redis-адаптер порта `CatalogCache` — cache-aside каталога под namespace `catalog:*`.

Ключи (логические, префикс `catalog:` навешивает адаптер): `home`, `categories`, `browse:…`
(Фаза 13). TTL задаёт вызывающий (политика кэша — данные в роутере). **Fail-open:** Redis
недоступен → `get` → None (эндпоинт соберёт из БД), `set`/`invalidate` — тихий no-op. Т.е.
падение Redis лишь снимает ускорение, отдачу каталога не ломает. `invalidate` чистит весь
namespace (`SCAN catalog:*` → `DEL`) — после `/add` устаревает и главная, и чипы, и страницы.
"""

from __future__ import annotations

import logging
from typing import cast

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.application.ports.catalog_cache import CatalogCache

logger = logging.getLogger(__name__)

_NS = "catalog:"


class RedisCatalogCache(CatalogCache):
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get(self, key: str) -> str | None:
        try:
            # decode_responses=True → строка; стабы redis типизируют шире (bytes|str|None).
            return cast("str | None", await self._redis.get(_NS + key))
        except RedisError:
            logger.warning("Redis catalog cache unavailable, failing open", exc_info=True)
            return None

    async def set(self, key: str, payload: str, ttl: int) -> None:
        try:
            await self._redis.set(_NS + key, payload, ex=ttl)
        except RedisError:
            logger.warning("Redis catalog cache unavailable, skipping set", exc_info=True)

    async def invalidate(self) -> None:
        try:
            # Сбрасываем весь namespace: SCAN не блокирует Redis (в отличие от KEYS).
            stale = [key async for key in self._redis.scan_iter(match=f"{_NS}*")]
            if stale:
                await self._redis.delete(*stale)
        except RedisError:
            logger.warning("Redis catalog cache unavailable, skipping invalidate", exc_info=True)
