"""Юнит-тесты CatalogService на фейковом репозитории (без БД, Фаза 13).

Проверяем логику сборки: клампы пагинации, исключение hero из «Жаңа түскен» и обрезку
полки, пропуск пустых полок, каноничный порядок категорий.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.application.services.catalog_service import (
    CATALOG_PAGE_MAX,
    HOME_SHELF_LIMIT,
    CatalogService,
)
from app.application.services.daily_service import DailyMovieService
from app.domain.catalog.daily import day_index, free_until
from app.domain.entities.movie import Movie

_NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


def _movie(mid: int, *, created_at: datetime | None = None) -> Movie:
    return Movie(
        id=mid,
        title_kk=f"M{mid}",
        description="d",
        categories=["disney"],
        poster_url="/p.jpg",
        telegram_file_id="fid",
        created_at=created_at,
    )


class _FakeMovies:
    """Мини-репозиторий: отдаёт заготовки, запоминает аргументы list_page."""

    def __init__(
        self,
        *,
        hero: Movie | None = None,
        pool: list[Movie] | None = None,
        recent: list[Movie] | None = None,
        popular: list[Movie] | None = None,
        page: tuple[list[Movie], int] = ([], 0),
        counts: dict[str, int] | None = None,
    ) -> None:
        self._pool = pool or ([hero] if hero is not None else [])
        self._recent = recent or []
        self._popular = popular or []
        self._page = page
        self._counts = counts or {}
        self.list_page_args: dict[str, object] = {}

    async def list_rotation_ids(self) -> list[int]:
        return [movie.id for movie in self._pool if movie.id is not None]

    async def get(self, movie_id: int) -> Movie | None:
        return next((m for m in self._pool if m.id == movie_id), None)

    async def list_recent(self, limit: int) -> list[Movie]:
        return self._recent[:limit]

    async def list_popular(self, limit: int) -> list[Movie]:
        return self._popular[:limit]

    async def list_page(
        self, *, categories: list[str], sort: str, direction: str, limit: int, offset: int
    ) -> tuple[list[Movie], int]:
        self.list_page_args = {
            "categories": categories,
            "sort": sort,
            "direction": direction,
            "limit": limit,
            "offset": offset,
        }
        return self._page

    async def category_counts(self) -> dict[str, int]:
        return self._counts


def _service(repo: _FakeMovies) -> CatalogService:
    """Каталог с настоящим `DailyMovieService` поверх того же фейка репозитория.

    Подменять выбор фильма дня заглушкой нельзя: витрина и выдача обязаны сходиться,
    и тест должен ломаться ровно тогда, когда они разъедутся.
    """
    return CatalogService(repo, DailyMovieService(repo))  # type: ignore[arg-type]


async def test_browse_clamps_page_and_limit() -> None:
    repo = _FakeMovies(page=([_movie(1)], 100))
    result = await _service(repo).browse(
        categories=["anime"], sort="rating", direction="asc", page=0, limit=999
    )

    assert result.page == 1                       # page ≥ 1
    assert result.limit == CATALOG_PAGE_MAX        # limit ≤ MAX (48)
    assert repo.list_page_args["offset"] == 0
    assert repo.list_page_args["limit"] == CATALOG_PAGE_MAX
    assert repo.list_page_args["categories"] == ["anime"]
    assert result.total == 100
    assert result.has_more is True                 # 1*48 < 100


async def test_browse_last_page_has_no_more() -> None:
    repo = _FakeMovies(page=([_movie(1)], 30))
    result = await _service(repo).browse(
        categories=[], sort="year", direction="desc", page=2, limit=24
    )

    assert repo.list_page_args["offset"] == 24     # (2-1)*24
    assert result.has_more is False                # 2*24=48 ≥ 30


async def test_home_excludes_hero_from_fresh_and_caps() -> None:
    recent = [_movie(mid) for mid in range(20, 0, -1)]  # id 20..1 (20 фильмов), новейший — hero
    repo = _FakeMovies(
        hero=_movie(20, created_at=_NOW - timedelta(hours=1)),  # свежий → закреплён
        recent=recent,
        popular=[_movie(5), _movie(6)],
    )

    home = await _service(repo).home(_NOW)

    assert home.hero is not None and home.hero.id == 20
    fresh, popular = home.shelves
    assert fresh.key == "fresh"
    assert len(fresh.movies) == HOME_SHELF_LIMIT           # обрезано до 14
    assert all(m.id != 20 for m in fresh.movies)           # hero исключён из «Жаңа түскен»
    assert popular.key == "popular"


async def test_home_skips_empty_shelves() -> None:
    home = await _service(_FakeMovies()).home(_NOW)
    assert home.hero is None
    assert home.shelves == []                               # пустые полки не добавляем


# --- hero = фильм дня ----------------------------------------------------

async def test_hero_is_the_daily_movie_from_the_whole_catalog() -> None:
    """Пул — весь каталог, а не только фильмы с баннером: hero живёт и на постере."""
    pool = [_movie(mid) for mid in (1, 2, 3, 4)]
    service = _service(_FakeMovies(pool=pool))
    start = _NOW + timedelta(days=-day_index(_NOW) % len(pool))

    picks = [await service.get_hero(start + timedelta(days=offset)) for offset in range(4)]
    ids = [movie.id for movie in picks if movie is not None]

    assert set(ids) == {1, 2, 3, 4}  # за круг каждый фильм выходит ровно раз
    # тот же день → тот же выбор (главная кэшируется и одна на всех)
    again = await service.get_hero(start)
    assert again is not None and again.id == ids[0]


async def test_home_reports_until_when_the_free_film_changes() -> None:
    """Витрина отдаёт срок бесплатности — фронту незачем считать часовой пояс самому."""
    home = await _service(_FakeMovies(pool=[_movie(1)])).home(_NOW)

    assert home.hero is not None
    assert home.free_until == free_until(_NOW)


async def test_empty_catalog_has_no_hero_and_no_deadline() -> None:
    home = await _service(_FakeMovies()).home(_NOW)

    assert home.hero is None
    assert home.free_until is None  # нечего показывать → нечему и истекать


async def test_category_counts_orders_canonically() -> None:
    repo = _FakeMovies(counts={"anime": 3, "disney": 5, "zzz_unknown": 2})
    result = await _service(repo).category_counts()

    # disney раньше anime в справочнике; незнакомая категория — в конец.
    assert result == [("disney", 5), ("anime", 3), ("zzz_unknown", 2)]
