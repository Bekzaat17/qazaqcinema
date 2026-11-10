from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import Callable
from typing import cast

from redis.asyncio import Redis
from redis.exceptions import RedisError, WatchError

logger = logging.getLogger(__name__)


class SystemGameRandom:
    def below(self, maximum: int) -> int:
        return secrets.randbelow(maximum)


class RedisRoomEvents:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def publish(self, code: str, revision: int) -> None:
        try:
            # Публикации после commit могут прийти не по порядку. WATCH сохраняет
            # максимальную версию и атомарность маркера с уведомлением подписчиков.
            key = f"board:revision:{code}"
            while True:
                async with self._redis.pipeline(transaction=True) as pipe:
                    try:
                        await pipe.watch(key)
                        latest = await pipe.get(key)
                        if latest is not None and int(latest) >= revision:
                            return
                        # redis-py не аннотирует синхронный переключатель транзакции.
                        cast(Callable[[], None], pipe.multi)()
                        pipe.set(key, revision, ex=86400)
                        pipe.publish(f"board:events:{code}", revision)
                        await pipe.execute()
                        return
                    except WatchError:
                        continue
        except (RedisError, ValueError):
            logger.exception("Сигнал обновления комнаты не доставлен")

    async def wait(self, code: str, revision: int, wait_seconds: int) -> None:
        try:
            async with self._redis.pubsub() as pubsub:
                await pubsub.subscribe(f"board:events:{code}")
                latest = await self._redis.get(f"board:revision:{code}")
                if latest is not None and int(latest) > revision:
                    return
                async with asyncio.timeout(wait_seconds):
                    async for event in pubsub.listen():
                        if event["type"] == "message":
                            return
        except TimeoutError:
            return
        except (RedisError, ValueError):
            logger.exception("Ожидание комнаты деградировало до короткого опроса")
            await asyncio.sleep(3)
