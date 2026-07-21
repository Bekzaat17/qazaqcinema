"""Каталог фильмов для Web App."""

from __future__ import annotations

from datetime import UTC, datetime

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import TypeAdapter

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit
from app.api.schemas.movie import (
    CatalogHomeOut,
    CategoryCountOut,
    MovieOut,
    MoviePageOut,
    PlayOut,
    ShelfOut,
)
from app.application.ports.catalog_cache import CatalogCache
from app.application.ports.repositories import SortDir, SortField
from app.application.services.catalog_service import CatalogService
from app.application.services.playback_service import PlaybackOutcome, PlaybackService
from app.domain.entities.user import User

# Казахские подписи полок главной (presentation — сервис отдаёт только ключи fresh/popular).
_SHELF_TITLES = {"fresh": "Жаңа түскен", "popular": "Танымал"}

# TTL кэша каталога (данные — политика кэша здесь; адаптер лишь исполняет). Главная и чипы
# меняются только на /add → живут долго; браузинг — много комбинаций и «по просмотрам» дрейфует
# с play_count → короткий TTL (бьёт и по объёму ключей, и по устареванию сортировки).
_HOME_TTL = 600
_CATEGORIES_TTL = 600
_BROWSE_TTL = 60
_CATEGORIES_ADAPTER = TypeAdapter(list[CategoryCountOut])

# Rate-limit (данные — крутить здесь): анти-скрейп каталога/поиска/просмотра на IP.
# Щедро (≈10 rps/IP): останавливает выкачку тысяч id, но не мешает живому юзеру и не
# бьёт по общему CGNAT-IP мобильной сети. Покрывает и /play (лежит в этом роутере).
_rate_limited = Depends(rate_limit(limit=100, window_seconds=10, scope="catalog"))

router = APIRouter(
    prefix="/api/movies",
    tags=["catalog"],
    route_class=DishkaRoute,
    dependencies=[_rate_limited],
)


@router.get("")
async def browse_movies(
    cache: FromDishka[CatalogCache],
    catalog: FromDishka[CatalogService],
    _user: User = Depends(get_current_user),
    categories: str | None = None,
    sort: SortField = "year",
    direction: SortDir = "desc",
    page: int = 1,
    limit: int = 24,
) -> Response:
    """Страница каталога: мультифильтр `?categories=a,b`, сортировка, пагинация (Фаза 13).

    Cache-aside (Redis, короткий TTL): ключ детерминирован по параметрам (категории дедупим и
    сортируем — порядок не влияет). Хит → сырой JSON; промах → БД + кэш. Клампы page/limit — в
    сервисе; сорт-поле/направление — Literal (422 на мусор). Корень префикса `/api/movies`.
    """
    selected = sorted({c for c in categories.split(",") if c}) if categories else []
    key = f"browse:{','.join(selected) or 'all'}:{sort}:{direction}:{page}:{limit}"
    cached = await cache.get(key)
    if cached is not None:
        return Response(content=cached, media_type="application/json")
    result = await catalog.browse(
        categories=selected, sort=sort, direction=direction, page=page, limit=limit
    )
    payload = MoviePageOut(
        items=[MovieOut.from_domain(movie) for movie in result.items],
        total=result.total,
        page=result.page,
        limit=result.limit,
        has_more=result.has_more,
    )
    body = payload.model_dump_json()
    await cache.set(key, body, _BROWSE_TTL)
    return Response(content=body, media_type="application/json")


@router.get("/search", response_model=list[MovieOut])
async def search_movies(
    catalog: FromDishka[CatalogService],
    q: str,
    _user: User = Depends(get_current_user),
) -> list[MovieOut]:
    movies = await catalog.search_movies(q)
    return [MovieOut.from_domain(movie) for movie in movies]


@router.get("/hero", response_model=MovieOut | None)
async def hero_movie(
    catalog: FromDishka[CatalogService],
    _user: User = Depends(get_current_user),
) -> MovieOut | None:
    """Фильм для hero главного экрана (выбор — на бэкенде: featured → новизна).

    Определён ДО `/{movie_id}`, иначе путь `hero` матчился бы как movie_id.
    """
    movie = await catalog.get_hero()
    return MovieOut.from_domain(movie) if movie is not None else None


@router.get("/home")
async def catalog_home(
    cache: FromDishka[CatalogCache],
    catalog: FromDishka[CatalogService],
    _user: User = Depends(get_current_user),
) -> Response:
    """Главный экран одним ответом (hero + готовые полки), cache-aside (Фаза 11.2/13).

    Хит — отдаём готовый JSON из Redis (ключ `home`); промах — собираем из БД (полки уже
    ограничены N на бэке), кладём в кэш. Инвалидируется при `/add`. Определён ДО `/{movie_id}`.
    Отдаём сырой `Response`, чтобы на хите не пересериализовывать кэш.
    """
    cached = await cache.get("home")
    if cached is not None:
        return Response(content=cached, media_type="application/json")
    home = await catalog.home()
    payload = CatalogHomeOut(
        hero=MovieOut.from_domain(home.hero) if home.hero is not None else None,
        shelves=[
            ShelfOut(
                key=shelf.key,
                title=_SHELF_TITLES.get(shelf.key, shelf.key),
                movies=[MovieOut.from_domain(movie) for movie in shelf.movies],
            )
            for shelf in home.shelves
        ],
    )
    body = payload.model_dump_json()
    await cache.set("home", body, _HOME_TTL)
    return Response(content=body, media_type="application/json")


@router.get("/categories")
async def list_categories(
    cache: FromDishka[CatalogCache],
    catalog: FromDishka[CatalogService],
    _user: User = Depends(get_current_user),
) -> Response:
    """Непустые категории со счётчиками для чипов (cache-aside). ДО `/{movie_id}`."""
    cached = await cache.get("categories")
    if cached is not None:
        return Response(content=cached, media_type="application/json")
    items = [
        CategoryCountOut(slug=slug, count=count)
        for slug, count in await catalog.category_counts()
    ]
    body = _CATEGORIES_ADAPTER.dump_json(items)
    await cache.set("categories", body.decode(), _CATEGORIES_TTL)
    return Response(content=body, media_type="application/json")


@router.get("/{movie_id}", response_model=MovieOut)
async def get_movie(
    movie_id: int,
    catalog: FromDishka[CatalogService],
    _user: User = Depends(get_current_user),
) -> MovieOut:
    movie = await catalog.get_movie(movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="movie not found")
    return MovieOut.from_domain(movie)


@router.post("/{movie_id}/play", response_model=PlayOut)
async def play_movie(
    movie_id: int,
    playback: FromDishka[PlaybackService],
    user: User = Depends(get_current_user),
) -> PlayOut:
    """Отправить защищённое видео подписчику в личку с ботом (protect_content).

    Видео уходит в Telegram-чат пользователя, НЕ через HTTP: API лишь триггерит отправку
    после initData-гейта. `telegram_file_id` наружу не отдаётся.
    """
    outcome = await playback.deliver(user, movie_id, datetime.now(UTC))
    if outcome is PlaybackOutcome.NO_ACCESS:
        raise HTTPException(status_code=403, detail="no_access")
    if outcome is PlaybackOutcome.NOT_FOUND:
        raise HTTPException(status_code=404, detail="movie not found")
    if outcome is PlaybackOutcome.BOT_BLOCKED:
        # Подписчик не открыл чат с ботом → бот не может доставить видео. Не 500 —
        # понятный код, фронт просит открыть бота и повторить.
        raise HTTPException(status_code=409, detail="bot_unreachable")
    return PlayOut(status="sent")
