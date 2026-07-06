"""Порт кэша каталога (DIP) — cache-aside для главной, чипов и страниц браузинга.

Один namespace `catalog:*` под несколько ключей (Фаза 13):
  - `home`        — главный экран (hero + полки), TTL ~600 c;
  - `categories`  — непустые категории со счётчиками (чипы), TTL ~600 c;
  - `browse:…`    — страница каталога по фильтру/сортировке, короткий TTL (много комбинаций;
                    TTL бьёт по объёму ключей и устареванию сорта «по просмотрам»).
Все — **fail-open**: Redis недоступен → `get` → None (эндпоинт соберёт из БД), `set`/`invalidate` —
тихий no-op. `invalidate` сбрасывает ВЕСЬ namespace (после `/add` новинка меняет и главную, и чипы,
и любую страницу). Кэшируем ТОЛЬКО JSON (постеры — статика). Namespace-префикс живёт в адаптере.
"""

from __future__ import annotations

from typing import Protocol


class CatalogCache(Protocol):
    async def get(self, key: str) -> str | None:
        """Готовый JSON по ключу или None (промах ИЛИ Redis недоступен → собрать из БД)."""
        ...

    async def set(self, key: str, payload: str, ttl: int) -> None:
        """Положить JSON под ключ на ttl секунд (при недоступном Redis — тихо пропустить)."""
        ...

    async def invalidate(self) -> None:
        """Сбросить ВЕСЬ кэш каталога (после `/add`, чтобы новинка появилась сразу)."""
        ...
