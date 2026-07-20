"""Юнит-тесты кэширования роутов каталога (cache-aside, Redis; Фазы 11.2/13).

Хит кэша → отдаём готовый JSON, БД не трогаем. Промах → собираем из БД + кладём в кэш под
свой ключ/TTL. Роуты зовём напрямую с фейками (TestClient/httpx в проекте нет).
"""

from __future__ import annotations

import json

from app.api.routers.catalog import browse_movies, catalog_home, list_categories
from app.application.services.catalog_service import BrowsePage, Home, HomeShelf
from app.domain.entities.movie import Movie
from app.domain.entities.user import User


def _movie(mid: int) -> Movie:
    return Movie(
        id=mid,
        title_kk=f"Фильм {mid}",
        description="сипаттама",
        categories=["disney"],
        poster_url=f"/posters/{mid}.jpg",
        telegram_file_id="ARCHIVE_FILE_ID",
    )


class _FakeCatalog:
    """Фейк CatalogService: отдаёт заготовки, считает обращения к БД-сборке."""

    def __init__(
        self,
        *,
        home: Home | None = None,
        page: BrowsePage | None = None,
        counts: list[tuple[str, int]] | None = None,
    ) -> None:
        self._home = home or Home(hero=None, shelves=[])
        self._page = page or BrowsePage(items=[], total=0, page=1, limit=24)
        self._counts = counts or []
        self.home_calls = 0
        self.browse_calls = 0
        self.counts_calls = 0

    async def home(self) -> Home:
        self.home_calls += 1
        return self._home

    async def browse(self, **kwargs: object) -> BrowsePage:
        self.browse_calls += 1
        return self._page

    async def category_counts(self) -> list[tuple[str, int]]:
        self.counts_calls += 1
        return self._counts


class _HitCache:
    """Всегда хит: get(любой ключ) → заготовленный JSON; set вызываться не должен."""

    def __init__(self, cached: str) -> None:
        self._cached = cached
        self.set_calls = 0

    async def get(self, key: str) -> str | None:
        return self._cached

    async def set(self, key: str, payload: str, ttl: int) -> None:
        self.set_calls += 1

    async def invalidate(self) -> None:
        pass


class _MissCache:
    """Промах-затем-хит: dict по ключам; фиксирует, что и с каким TTL положили."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, payload: str, ttl: int) -> None:
        self.store[key] = payload
        self.ttls[key] = ttl

    async def invalidate(self) -> None:
        self.store.clear()


_USER = User(telegram_id=1)


# --- /home ---------------------------------------------------------------

async def test_home_returns_cached_without_touching_db() -> None:
    cache = _HitCache('{"hero":null,"shelves":[]}')
    catalog = _FakeCatalog()

    response = await catalog_home(cache=cache, catalog=catalog, _user=_USER)

    assert response.body == b'{"hero":null,"shelves":[]}'
    assert catalog.home_calls == 0  # хит кэша → БД не читаем
    assert cache.set_calls == 0


async def test_home_builds_from_db_and_caches_on_miss() -> None:
    cache = _MissCache()
    home = Home(hero=_movie(2), shelves=[HomeShelf(key="fresh", movies=[_movie(2), _movie(1)])])
    catalog = _FakeCatalog(home=home)

    response = await catalog_home(cache=cache, catalog=catalog, _user=_USER)

    assert catalog.home_calls == 1
    payload = json.loads(response.body)
    assert payload["hero"]["id"] == 2
    assert payload["shelves"][0]["key"] == "fresh"
    assert payload["shelves"][0]["title"] == "Жаңа түскен"  # ключ → казахская подпись на бэке
    assert [m["id"] for m in payload["shelves"][0]["movies"]] == [2, 1]
    assert cache.store["home"] is not None                   # результат положен в кэш под "home"
    assert "telegram_file_id" not in response.body.decode()  # DTO не утекает file_id


# --- /api/movies (браузинг) ----------------------------------------------

async def test_browse_returns_cached_without_touching_db() -> None:
    cache = _HitCache('{"items":[],"total":0,"page":1,"limit":24,"has_more":false}')
    catalog = _FakeCatalog()

    response = await browse_movies(
        cache=cache, catalog=catalog, _user=_USER,
        categories="anime", sort="date", direction="desc", page=1, limit=24,
    )

    assert response.body == b'{"items":[],"total":0,"page":1,"limit":24,"has_more":false}'
    assert catalog.browse_calls == 0  # хит кэша → БД не читаем
    assert cache.set_calls == 0


async def test_browse_builds_and_caches_on_miss_with_stable_key() -> None:
    cache = _MissCache()
    catalog = _FakeCatalog(page=BrowsePage(items=[_movie(3)], total=1, page=1, limit=24))

    response = await browse_movies(
        cache=cache, catalog=catalog, _user=_USER,
        categories="disney,anime", sort="rating", direction="asc", page=1, limit=24,
    )

    assert catalog.browse_calls == 1
    payload = json.loads(response.body)
    assert [m["id"] for m in payload["items"]] == [3]
    assert payload["total"] == 1
    key = "browse:anime,disney:rating:asc:1:24"  # категории дедуплены+сортированы → стабильный ключ
    assert key in cache.store
    assert cache.ttls[key] == 60                             # короткий TTL браузинга
    assert "telegram_file_id" not in response.body.decode()


# --- /api/movies/categories ----------------------------------------------

async def test_categories_cache_aside() -> None:
    cache = _MissCache()
    catalog = _FakeCatalog(counts=[("disney", 2), ("anime", 1)])

    response = await list_categories(cache=cache, catalog=catalog, _user=_USER)

    assert catalog.counts_calls == 1
    assert json.loads(response.body) == [
        {"slug": "disney", "count": 2},
        {"slug": "anime", "count": 1},
    ]
    assert "categories" in cache.store

    await list_categories(cache=cache, catalog=catalog, _user=_USER)  # второй заход — из кэша
    assert catalog.counts_calls == 1
