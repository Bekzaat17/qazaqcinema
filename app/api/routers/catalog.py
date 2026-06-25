"""Каталог фильмов для Web App."""

from __future__ import annotations

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, HTTPException

from app.api.schemas.movie import MovieOut
from app.application.services.catalog_service import CatalogService

router = APIRouter(prefix="/api/movies", tags=["catalog"], route_class=DishkaRoute)


@router.get("", response_model=list[MovieOut])
async def list_movies(
    catalog: FromDishka[CatalogService], category: str | None = None
) -> list[MovieOut]:
    movies = await catalog.list_movies(category)
    return [MovieOut.from_domain(movie) for movie in movies]


@router.get("/search", response_model=list[MovieOut])
async def search_movies(catalog: FromDishka[CatalogService], q: str) -> list[MovieOut]:
    movies = await catalog.search_movies(q)
    return [MovieOut.from_domain(movie) for movie in movies]


@router.get("/{movie_id}", response_model=MovieOut)
async def get_movie(movie_id: int, catalog: FromDishka[CatalogService]) -> MovieOut:
    movie = await catalog.get_movie(movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="movie not found")
    return MovieOut.from_domain(movie)
