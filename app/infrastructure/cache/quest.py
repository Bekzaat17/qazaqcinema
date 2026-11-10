from __future__ import annotations

import json
import logging
from dataclasses import asdict

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.domain.quest.game import RankEntry

logger = logging.getLogger(__name__)


class RedisQuestRankingCache:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get(self, key: str) -> tuple[RankEntry, ...] | None:
        try:
            raw = await self._redis.get(f"quest:ranking:{key}")
            if raw is None:
                return None
            return tuple(
                RankEntry(int(row["user_id"]), int(row["rank"]), int(row["points"]))
                for row in json.loads(raw)
            )
        except (RedisError, ValueError, TypeError, KeyError):
            logger.warning("Кэш рейтинга недоступен", exc_info=True)
            return None

    async def set(self, key: str, entries: tuple[RankEntry, ...], ttl: int) -> None:
        try:
            await self._redis.set(
                f"quest:ranking:{key}", json.dumps([asdict(e) for e in entries]), ex=ttl
            )
        except RedisError:
            logger.warning("Рейтинг не закэширован", exc_info=True)
