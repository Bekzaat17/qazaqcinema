"""Избранное («Таңдаулы»): третья вкладка Mini App.

Отдельный роутер, а не ручки внутри `catalog`, по одной причине: ответы каталога
кэшируются в Redis ОДНИ НА ВСЕХ, а здесь всё персональное. Держать их рядом — верный
способ однажды закэшировать чужой список.

Гейта подписки тут нет намеренно: звезду ставит любой авторизованный пользователь.
"""

from __future__ import annotations

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit
from app.api.schemas.movie import MovieOut
from app.application.services.favorite_service import FavoriteService
from app.domain.entities.user import User

# Rate-limit (данные): тумблер звезды — write-ручка, лимит как у прочих мутирующих
# (payments/me). Чтение списка — щедрее: фронт дёргает `ids` на каждом открытии вкладок,
# а ключ лимитера — IP, за которым сидит вся мобильная вышка (CGNAT).
_write_rate_limited = Depends(rate_limit(limit=60, window_seconds=60, scope="favorites"))
_read_rate_limited = Depends(rate_limit(limit=120, window_seconds=60, scope="favorites_read"))

router = APIRouter(prefix="/api/favorites", tags=["favorites"], route_class=DishkaRoute)


class FavoriteIdsOut(BaseModel):
    """Только id избранного — лёгкий ответ для закраски звёзд в лентах."""

    ids: list[int]


@router.get("", response_model=list[MovieOut], dependencies=[_read_rate_limited])
async def list_favorites(
    favorites: FromDishka[FavoriteService],
    user: User = Depends(get_current_user),
) -> list[MovieOut]:
    """Избранное текущего юзера, свежедобавленные сверху (содержимое вкладки)."""
    movies = await favorites.list_for_user(user.telegram_id)
    return [MovieOut.from_domain(movie) for movie in movies]


@router.get("/ids", response_model=FavoriteIdsOut, dependencies=[_read_rate_limited])
async def list_favorite_ids(
    favorites: FromDishka[FavoriteService],
    user: User = Depends(get_current_user),
) -> FavoriteIdsOut:
    """id избранного одним списком.

    Фронт держит их множеством и закрашивает звёзды в полках и каталоге, не запрашивая
    карточки повторно. Персональный флаг внутри самих карточек невозможен — они общие
    для всех и лежат в кэше.
    """
    return FavoriteIdsOut(ids=await favorites.list_ids(user.telegram_id))


@router.put("/{movie_id}", status_code=204, dependencies=[_write_rate_limited])
async def add_favorite(
    movie_id: int,
    favorites: FromDishka[FavoriteService],
    user: User = Depends(get_current_user),
) -> None:
    """Поставить звезду. PUT (а не POST) — операция идемпотентна: повтор ничего не меняет."""
    if not await favorites.add(user.telegram_id, movie_id):
        raise HTTPException(status_code=404, detail="movie not found")


@router.delete("/{movie_id}", status_code=204, dependencies=[_write_rate_limited])
async def remove_favorite(
    movie_id: int,
    favorites: FromDishka[FavoriteService],
    user: User = Depends(get_current_user),
) -> None:
    """Снять звезду. Отсутствие фильма в списке — не ошибка (тоже идемпотентно)."""
    await favorites.remove(user.telegram_id, movie_id)
