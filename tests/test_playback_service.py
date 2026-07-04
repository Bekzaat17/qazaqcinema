"""Юнит-тест PlaybackService на фейках (без БД и aiogram).

Проверяем ядро безопасности: видео уходит ТОЛЬКО подписчику; без доступа фильм даже
не загружается; несуществующий фильм → NOT_FOUND без отправки.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.application.services.playback_service import PlaybackOutcome, PlaybackService
from app.domain.entities.enums import UserStatus
from app.domain.entities.movie import Movie
from app.domain.entities.user import User

_NOW = datetime(2026, 6, 29, tzinfo=UTC)


def _movie() -> Movie:
    return Movie(
        id=7,
        title_kk="Фильм",
        description="сипаттама",
        category="disney",
        poster_url="/posters/x.jpg",
        telegram_file_id="ARCHIVE_FILE_ID",
    )


class _FakeMovies:
    def __init__(self, movie: Movie | None) -> None:
        self._movie = movie
        self.get_calls: list[int] = []

    async def get(self, movie_id: int) -> Movie | None:
        self.get_calls.append(movie_id)
        return self._movie


class _FakeNotifier:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str, str | None]] = []

    async def send_protected_video(
        self, chat_id: int, file_id: str, caption: str | None = None
    ) -> None:
        self.sent.append((chat_id, file_id, caption))


class _OneShotLock:
    """Эмулирует Redis SET NX: первый acquire ключа — успех, повтор — занято."""

    def __init__(self) -> None:
        self._taken: set[str] = set()
        self.keys: list[str] = []

    async def acquire(self, key: str, ttl_seconds: int) -> bool:
        self.keys.append(key)
        if key in self._taken:
            return False
        self._taken.add(key)
        return True


def _user(status: UserStatus, expires_at: datetime | None) -> User:
    return User(telegram_id=42, status=status, expires_at=expires_at)


async def test_deliver_sends_protected_video_for_active_subscriber() -> None:
    movies = _FakeMovies(_movie())
    notifier = _FakeNotifier()
    service = PlaybackService(movies, notifier, _OneShotLock())

    outcome = await service.deliver(
        _user(UserStatus.ACTIVE, _NOW + timedelta(days=1)), movie_id=7, now=_NOW
    )

    assert outcome is PlaybackOutcome.DELIVERED
    assert notifier.sent == [(42, "ARCHIVE_FILE_ID", "Фильм")]


async def test_deliver_denies_without_access_and_skips_movie_load() -> None:
    movies = _FakeMovies(_movie())
    notifier = _FakeNotifier()
    service = PlaybackService(movies, notifier, _OneShotLock())

    outcome = await service.deliver(
        _user(UserStatus.EXPIRED, _NOW - timedelta(days=1)), movie_id=7, now=_NOW
    )

    assert outcome is PlaybackOutcome.NO_ACCESS
    assert notifier.sent == []
    assert movies.get_calls == []  # без доступа фильм не раскрываем


async def test_deliver_not_found_when_movie_missing() -> None:
    movies = _FakeMovies(None)
    notifier = _FakeNotifier()
    service = PlaybackService(movies, notifier, _OneShotLock())

    outcome = await service.deliver(
        _user(UserStatus.ACTIVE, _NOW + timedelta(days=1)), movie_id=99, now=_NOW
    )

    assert outcome is PlaybackOutcome.NOT_FOUND
    assert notifier.sent == []


async def test_deliver_swallows_rapid_duplicate_send() -> None:
    """Двойной клик «Көру» (тот же юзер+фильм) в окне лока → ОДНА отправка (11.4)."""
    movies = _FakeMovies(_movie())
    notifier = _FakeNotifier()
    lock = _OneShotLock()
    service = PlaybackService(movies, notifier, lock)
    active = _user(UserStatus.ACTIVE, _NOW + timedelta(days=1))

    first = await service.deliver(active, movie_id=7, now=_NOW)
    second = await service.deliver(active, movie_id=7, now=_NOW)

    assert first is PlaybackOutcome.DELIVERED
    assert second is PlaybackOutcome.DELIVERED  # повтор не ошибка — та же модалка на фронте
    assert notifier.sent == [(42, "ARCHIVE_FILE_ID", "Фильм")]  # но отправка одна
    assert lock.keys == ["send_video:42:7", "send_video:42:7"]
