"""Redis-кэш проверки подписки на канал — декоратор над `ChannelMembership`.

Проверку спрашивает КАЖДЫЙ тап по «Көру» у неподписчика, а `getChatMember` — сетевой
вызов к Telegram, идущий в общие лимиты бота. Без кэша один человек, листающий каталог,
тратил бы их за всех.

Кэшируем ТОЛЬКО «подписан». Отказ живёт до следующего вопроса, и это не экономия
наоборот, а сценарий: человек видит «жазылыңыз», уходит в канал, возвращается и жмёт
«Тексеру» — закэшируй мы отказ, он увидел бы его снова, уже будучи подписчиком. Отказов
при этом мало: их порождают только осознанные нажатия, а не листание.

TTL 5 минут — компромисс: отписавшийся не ходит бесплатно сутки, а листание каталога не
жжёт лимиты. Redis лёг → спрашиваем Telegram напрямую: кэш не имеет права быть точкой
отказа (то же правило, что у `RedisDailyPin` и `RedisCatalogCache`).
"""

from __future__ import annotations

import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.application.ports.channel import ChannelMembership

logger = logging.getLogger(__name__)

_PREFIX = "channel:member:"
DEFAULT_TTL_SECONDS = 300


class CachedChannelMembership:
    def __init__(
        self, inner: ChannelMembership, redis: Redis, ttl_seconds: int = DEFAULT_TTL_SECONDS
    ) -> None:
        self._inner = inner
        self._redis = redis
        self._ttl = max(ttl_seconds, 1)

    async def is_member(self, user_id: int) -> bool:
        key = f"{_PREFIX}{user_id}"
        try:
            if await self._redis.get(key) is not None:
                return True
        except RedisError:
            logger.warning("Redis недоступен, подписку спрашиваем у Telegram", exc_info=True)

        member = await self._inner.is_member(user_id)
        if member:
            try:
                await self._redis.set(key, 1, ex=self._ttl)
            except RedisError:
                logger.warning("Redis недоступен, подписка не закэширована", exc_info=True)
        return member

    async def count_members(self) -> int | None:
        """Без кэша: зовётся раз в сутки из отчёта, и свежесть тут важнее экономии."""
        return await self._inner.count_members()
