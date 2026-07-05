"""Redis-адаптер порта `SessionStore` — серверные сессии Web App.

Ключ `session:<uuid>` → JSON `{user_id, username}`, TTL 24 ч. Токен — `uuid4().hex`
(122 бита случайности, неугадываем). **Fail-open:** Redis недоступен → `create` → None,
`get` → None; вызывающий откатывается на stateless-initData (см. `api/deps/auth.py`),
поэтому падение Redis не ломает авторизацию.
"""

from __future__ import annotations

import json
import logging
from uuid import uuid4

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.application.ports.session import Session, SessionStore

logger = logging.getLogger(__name__)

_PREFIX = "session:"
_TTL_SECONDS = 24 * 60 * 60


class RedisSessionStore(SessionStore):
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def create(self, user_id: int, username: str | None) -> str | None:
        token = uuid4().hex
        payload = json.dumps({"user_id": user_id, "username": username})
        try:
            await self._redis.set(f"{_PREFIX}{token}", payload, ex=_TTL_SECONDS)
        except RedisError:
            logger.warning("Redis session store unavailable, failing open", exc_info=True)
            return None
        return token

    async def get(self, token: str) -> Session | None:
        try:
            raw = await self._redis.get(f"{_PREFIX}{token}")
        except RedisError:
            logger.warning("Redis session store unavailable, failing open", exc_info=True)
            return None
        if raw is None:
            return None
        data = json.loads(raw)
        return Session(user_id=int(data["user_id"]), username=data.get("username"))
