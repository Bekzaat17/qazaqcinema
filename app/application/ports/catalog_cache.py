"""Порт кэша агрегированного каталога (DIP).

Главный экран (hero + все фильмы) — один JSON, кэшируется на короткий TTL, чтобы не
собирать его из БД на каждый заход. Инвалидируется при добавлении фильма (`/add`),
иначе новинка не видна до истечения TTL. Кэшируем ТОЛЬКО JSON (постеры — статика).
Реализация — `infrastructure/cache/catalog.py` (Redis `catalog:main` EX 600).
"""

from __future__ import annotations

from typing import Protocol


class CatalogCache(Protocol):
    async def get(self) -> str | None:
        """Готовый JSON главной или None (промах кэша ИЛИ Redis недоступен → собрать из БД)."""
        ...

    async def set(self, payload: str) -> None:
        """Положить JSON главной в кэш на TTL (при недоступном Redis — тихо пропустить)."""
        ...

    async def invalidate(self) -> None:
        """Сбросить кэш главной (после `/add`, чтобы новинка появилась сразу)."""
        ...
