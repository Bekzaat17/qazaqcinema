"""Юнит-тест эндпоинта `/home` (cache-aside, Фаза 11.2).

Хит кэша → отдаём готовый JSON, БД не трогаем. Промах → собираем из БД, кладём в кэш.
Эндпоинт зовём напрямую с фейками (TestClient/httpx в проекте нет).
"""

from __future__ import annotations

import json

from app.api.routers.catalog import catalog_home
from app.domain.entities.movie import Movie
from app.domain.entities.user import User


def _movie(mid: int) -> Movie:
    return Movie(
        id=mid,
        title_kk=f"Фильм {mid}",
        description="сипаттама",
        category="disney",
        poster_url=f"/posters/{mid}.jpg",
        telegram_file_id="ARCHIVE_FILE_ID",
    )


class _FakeCatalog:
    def __init__(self, movies: list[Movie], hero: Movie | None) -> None:
        self._movies = movies
        self._hero = hero
        self.list_calls = 0

    async def list_movies(self, category: str | None = None) -> list[Movie]:
        self.list_calls += 1
        return self._movies

    async def get_hero(self) -> Movie | None:
        return self._hero


class _HitCache:
    def __init__(self, cached: str) -> None:
        self._cached = cached
        self.set_calls = 0

    async def get(self) -> str | None:
        return self._cached

    async def set(self, payload: str) -> None:
        self.set_calls += 1

    async def invalidate(self) -> None:
        pass


class _MissCache:
    def __init__(self) -> None:
        self.stored: str | None = None

    async def get(self) -> str | None:
        return self.stored

    async def set(self, payload: str) -> None:
        self.stored = payload

    async def invalidate(self) -> None:
        self.stored = None


async def test_home_returns_cached_without_touching_db() -> None:
    cache = _HitCache('{"hero":null,"movies":[]}')
    catalog = _FakeCatalog([_movie(1)], None)

    response = await catalog_home(cache=cache, catalog=catalog, _user=User(telegram_id=1))

    assert response.body == b'{"hero":null,"movies":[]}'
    assert catalog.list_calls == 0  # хит кэша → БД не читаем
    assert cache.set_calls == 0


async def test_home_builds_from_db_and_caches_on_miss() -> None:
    cache = _MissCache()
    catalog = _FakeCatalog([_movie(2), _movie(1)], _movie(2))

    response = await catalog_home(cache=cache, catalog=catalog, _user=User(telegram_id=1))

    assert catalog.list_calls == 1
    payload = json.loads(response.body)
    assert payload["hero"]["id"] == 2
    assert [m["id"] for m in payload["movies"]] == [2, 1]
    assert cache.stored is not None                        # результат положен в кэш
    assert "telegram_file_id" not in response.body.decode()  # DTO не утекает file_id
