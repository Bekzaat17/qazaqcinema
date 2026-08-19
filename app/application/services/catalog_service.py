"""Каталог фильмов для Web App. telegram_file_id наружу не отдаётся (см. API-схемы).

Главную (полки) и каталог (страницы) собирает и ОГРАНИЧИВАЕТ сервер: главная — hero +
последние N на полку, каталог — страница по фильтру/сортировке. Клиент получает ровно
то, что рисует; размер ответа /home не растёт с каталогом (Фаза 13).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.ports.repositories import MovieRepository, SortDir, SortField
from app.application.services.daily_service import DailyMovieService
from app.domain.catalog.categories import CATEGORIES
from app.domain.catalog.daily import free_until
from app.domain.entities.movie import Movie

# Сколько фильмов на полке главной (последние N; полка «Танымал» — топ N по просмотрам).
HOME_SHELF_LIMIT = 14
# Пагинация каталога: дефолтный и максимальный размер страницы (клампим внутри browse).
CATALOG_PAGE_DEFAULT = 24
CATALOG_PAGE_MAX = 48


@dataclass(frozen=True, slots=True)
class HomeShelf:
    """Готовая полка главной: ключ (fresh/popular) + фильмы. Подпись даёт presentation."""

    key: str
    movies: list[Movie]


@dataclass(frozen=True, slots=True)
class Home:
    """Содержимое главного экрана: фильм дня (hero) + полки (собрано и ограничено на бэке).

    `free_until` — до какого момента hero бесплатен (ближайшая местная полночь). Момент
    считает бэк, а не фронт: правило суток живёт в `domain/catalog/daily`, и обратный
    отсчёт на экране обязан сходиться с тем, что реально пустит `PlaybackService`.
    """

    hero: Movie | None
    free_until: datetime | None
    shelves: list[HomeShelf]


@dataclass(frozen=True, slots=True)
class BrowsePage:
    """Страница каталога: срез + total (для пагинации). page/limit — уже клампнутые."""

    items: list[Movie]
    total: int
    page: int
    limit: int

    @property
    def has_more(self) -> bool:
        # Через эту страницу «просмотрено» page*limit позиций; меньше total → есть ещё.
        return self.page * self.limit < self.total


class CatalogService:
    def __init__(self, movies: MovieRepository, daily: DailyMovieService) -> None:
        self._movies = movies
        self._daily = daily

    async def home(self, now: datetime) -> Home:
        """Главная: фильм дня + «Жаңа түскен» (последние N) + «Танымал» (топ N по просмотрам).

        Hero исключаем из «Жаңа түскен» (он уже крупно наверху) — берём N+1 и отбрасываем.
        Пустые полки не добавляем (мелкий каталог не рисует пустые ряды).
        """
        hero = await self.get_hero(now)
        hero_id = hero.id if hero is not None else None
        recent = await self._movies.list_recent(HOME_SHELF_LIMIT + 1)
        fresh = [m for m in recent if m.id != hero_id][:HOME_SHELF_LIMIT]
        popular = await self._movies.list_popular(HOME_SHELF_LIMIT)

        shelves: list[HomeShelf] = []
        if fresh:
            shelves.append(HomeShelf(key="fresh", movies=fresh))
        if popular:
            shelves.append(HomeShelf(key="popular", movies=popular))
        return Home(
            hero=hero,
            free_until=None if hero is None else free_until(now),
            shelves=shelves,
        )

    async def browse(
        self,
        *,
        categories: list[str],
        sort: SortField,
        direction: SortDir,
        page: int,
        limit: int,
    ) -> BrowsePage:
        """Страница каталога по фильтру/сортировке. Клампы (page≥1, limit≤MAX) — здесь."""
        limit = max(1, min(limit, CATALOG_PAGE_MAX))
        page = max(1, page)
        items, total = await self._movies.list_page(
            categories=categories,
            sort=sort,
            direction=direction,
            limit=limit,
            offset=(page - 1) * limit,
        )
        return BrowsePage(items=items, total=total, page=page, limit=limit)

    async def category_counts(self) -> list[tuple[str, int]]:
        """Непустые категории со счётчиками для чипов каталога, в каноничном порядке.

        Порядок берём из справочника CATEGORIES (тип → аудитория → жанр), незнакомые
        (которых в справочнике нет) — в конец, чтобы чип не потерялся.
        """
        counts = await self._movies.category_counts()
        known = [(slug, counts[slug]) for slug in CATEGORIES if slug in counts]
        extra = [(slug, count) for slug, count in counts.items() if slug not in CATEGORIES]
        return known + extra

    async def search_movies(self, query: str) -> list[Movie]:
        normalized = query.strip()
        if not normalized:
            return []
        return await self._movies.search(normalized)

    async def get_movie(self, movie_id: int) -> Movie | None:
        return await self._movies.get(movie_id)

    async def all_movies(self) -> list[Movie]:
        """Все фильмы (для публичного sitemap/каталог-хаба SEO). Порядок — как у репозитория."""
        return await self._movies.list_all()

    async def get_hero(self, now: datetime) -> Movie | None:
        """Hero главной = фильм дня (решение 2026-08-19).

        Курирования тут больше нет: раньше наверху висел свежайший `is_featured`, и это
        была просто красивая карточка, которая упиралась в пэйволл. Теперь первый экран
        показывает то, что сегодня можно посмотреть бесплатно, — и потому источник
        правды один на витрину и на выдачу (`DailyMovieService`).
        """
        return await self._daily.today(now)
