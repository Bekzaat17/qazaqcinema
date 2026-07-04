"""Каталог фильмов для Web App."""

from __future__ import annotations

from datetime import UTC, datetime

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit
from app.api.schemas.movie import MovieOut, PlayOut
from app.application.services.catalog_service import CatalogService
from app.application.services.playback_service import PlaybackOutcome, PlaybackService
from app.domain.entities.user import User

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


@router.get("", response_model=list[MovieOut])
async def list_movies(
    catalog: FromDishka[CatalogService],
    _user: User = Depends(get_current_user),
    category: str | None = None,
) -> list[MovieOut]:
    movies = await catalog.list_movies(category)
    return [MovieOut.from_domain(movie) for movie in movies]


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
    return PlayOut(status="sent")
