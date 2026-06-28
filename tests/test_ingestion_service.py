"""Юнит-тест MovieIngestionService на фейковых портах (без БД и aiogram)."""

from __future__ import annotations

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
        return f"/posters/fake.{ext}"


class _FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def notify_admins(self, text: str) -> None:
        self.messages.append(text)


async def test_ingest_saves_poster_persists_and_notifies() -> None:
    movies = _FakeMovies()
    posters = _FakePosters()
    notifier = _FakeNotifier()
    service = MovieIngestionService(movies, notifier, posters)

    movie = await service.ingest(
        title_kk="Арыстан Патша",
        title_ru="Король Лев",
        title_original="The Lion King",
        category="disney",
        description="сипаттама",
        year=1994,
        rating=8.5,
        video_file_id="archive-file-id",
        poster_bytes=b"image-bytes",
    )

    assert movie.id == 1
    assert movie.poster_url == "/posters/fake.jpg"   # постер ушёл в хранилище
    assert movie.telegram_file_id == "archive-file-id"
    assert posters.saved == [b"image-bytes"]
    assert movies.added[0].title_ru == "Король Лев"
    assert any("Арыстан Патша" in message for message in notifier.messages)
