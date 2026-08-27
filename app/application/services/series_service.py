"""Сериалы и сезоны: справочник поверх `SeriesRepository`/`SeasonRepository`.

Сериал — только название (группировка сезонов). Постер/название/категории/описание
живут на сезоне (решение 2026-08-28) — спрашиваются один раз при его создании, как у
обычного фильма; серии внутри сезона своего названия не имеют, только номер (см.
`MovieIngestionService.ingest`, который копирует эти поля на каждую серию).
"""

from __future__ import annotations

from app.application.ports.images import POSTER, ImageProcessor
from app.application.ports.repositories import SeasonRepository, SeriesRepository
from app.application.ports.storage import PosterStorage
from app.domain.entities.season import Season
from app.domain.entities.series import Series


class SeriesService:
    def __init__(
        self,
        series: SeriesRepository,
        seasons: SeasonRepository,
        posters: PosterStorage,
        images: ImageProcessor,
    ) -> None:
        self._series = series
        self._seasons = seasons
        self._posters = posters
        self._images = images

    async def list_series(self) -> list[Series]:
        return await self._series.list_all()

    async def get_series(self, series_id: int) -> Series | None:
        return await self._series.get(series_id)

    async def list_seasons(self, series_id: int) -> list[Season]:
        return await self._seasons.list_by_series(series_id)

    async def get_season(self, season_id: int) -> Season | None:
        return await self._seasons.get(season_id)

    async def create_series(self, title_kk: str) -> Series:
        return await self._series.add(Series(title_kk=title_kk))

    async def create_season(
        self,
        series_id: int,
        season_number: int,
        poster_bytes: bytes,
        *,
        title_kk: str,
        description: str,
        categories: list[str],
    ) -> Season:
        """Новый сезон: постер нормализуется/сохраняется здесь же (единственный раз)."""
        poster_url = await self._posters.save(await self._images.normalize(poster_bytes, POSTER))
        return await self._seasons.add(
            Season(
                series_id=series_id,
                season_number=season_number,
                poster_url=poster_url,
                title_kk=title_kk,
                description=description,
                categories=categories,
            )
        )
