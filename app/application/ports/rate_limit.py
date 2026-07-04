"""Порт ограничителя частоты запросов (DIP).

Фиксированное окно: не более `limit` обращений за `window_seconds` на ключ (обычно —
IP клиента, позже — юзер из сессии, Фаза 11.1). Защищает API от выкачки каталога и
спама. Реализация — `infrastructure/cache/rate_limiter.py` (Redis `INCR`/`EXPIRE`).
"""

from __future__ import annotations

from typing import Protocol


class RateLimiter(Protocol):
    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        """Регистрирует одно обращение по `key`.

        True  — в пределах лимита (запрос пропустить).
        False — лимит `limit` за окно `window_seconds` исчерпан (→ 429).
        """
        ...
