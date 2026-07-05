"""Юнит-тест MovieIngestionService на фейковых портах (без БД и aiogram)."""

from __future__ import annotations

from app.application.ports.images import HERO, POSTER, ImageSpec
from app.application.services.ingestion_service import MovieIngestionService
from app.domain.entities.movie import Movie


class _FakeMovies:
    def __init__(self) -> None:
        self.added: list[Movie] = []

    async def add(self, movie: Movie) -> Movie:
        movie.id = len(self.added) + 1
        self.added.append(movie)
        return movie


class _FakePosters:
    def __init__(self) -> None:
        self.saved: list[bytes] = []

    async def save(self, data: bytes, ext: str = "jpg") -> str:
        self.saved.append(data)
        return f"/posters/fake{len(self.saved)}.{ext}"


class _FakeImages:
    def __init__(self) -> None:
        self.calls: list[tuple[bytes, ImageSpec]] = []

    async def normalize(self, data: bytes, spec: ImageSpec) -> bytes:
        self.calls.append((data, spec))
        return data  # в тесте пиксели не трогаем — важен факт вызова и spec


class _FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def notify_admins(self, text: str) -> None:
        self.messages.append(text)


class _FakeCache:
    def __init__(self) -> None:
        self.invalidated = 0

    async def get(self) -> str | None:
        return None

    async def set(self, payload: str) -> None:
        pass

    async def invalidate(self) -> None:
        self.invalidated += 1


async def test_ingest_saves_poster_persists_and_notifies() -> None:
    movies = _FakeMovies()
    posters = _FakePosters()
    images = _FakeImages()
    notifier = _FakeNotifier()
    cache = _FakeCache()
    service = MovieIngestionService(movies, notifier, posters, images, cache)

    movie = await service.ingest(
        title_kk="Арыстан Патша",
        title_ru="Король Лев",
        title_original="The Lion King",
        category="disney",
        description="сипаттама",
        year=1994,
        rating=8.5,
        is_featured=False,
        video_file_id="archive-file-id",
        poster_bytes=b"image-bytes",
        hero_bytes=None,
    )

    assert movie.id == 1
    assert movie.telegram_file_id == "archive-file-id"
    assert movie.is_featured is False
    assert movie.hero_image_url is None                # без баннера hero пуст
    assert posters.saved == [b"image-bytes"]           # только постер
    assert images.calls == [(b"image-bytes", POSTER)]  # нормализован к 2:3
    assert movies.added[0].title_ru == "Король Лев"
    assert any("Арыстан Патша" in message for message in notifier.messages)
    assert cache.invalidated == 1                       # кэш главной сброшен → новинка видна


async def test_ingest_featured_saves_hero_banner() -> None:
    movies = _FakeMovies()
    posters = _FakePosters()
    images = _FakeImages()
    notifier = _FakeNotifier()
    service = MovieIngestionService(movies, notifier, posters, images, _FakeCache())

    movie = await service.ingest(
        title_kk="Наруто",
        title_ru=None,
        title_original="Naruto",
        category="anime",
        description="сипаттама",
        year=2002,
        rating=8.3,
        is_featured=True,
        video_file_id="vid",
        poster_bytes=b"poster",
        hero_bytes=b"hero",
    )

    assert movie.is_featured is True
    assert movie.hero_image_url is not None                      # баннер сохранён
    assert posters.saved == [b"poster", b"hero"]                 # постер + hero
    assert {spec for _, spec in images.calls} == {POSTER, HERO}  # обе нормализованы
