"""Юнит-тест PlaybackService на фейках (без БД и aiogram).

Проверяем ядро безопасности: видео уходит ТОЛЬКО подписчику; без доступа фильм даже
не загружается; несуществующий фильм → NOT_FOUND без отправки.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.application.ports.telegram import RecipientUnreachableError
from app.application.services.playback_service import PlaybackOutcome, PlaybackService
from app.domain.entities.delivery import VideoDelivery
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
        self.play_increments: list[int] = []

    async def get(self, movie_id: int) -> Movie | None:
        self.get_calls.append(movie_id)
        return self._movie

    async def increment_play_count(self, movie_id: int) -> None:
        self.play_increments.append(movie_id)


class _FakeNotifier:
    def __init__(self, unreachable: bool = False) -> None:
        self.sent: list[tuple[int, str, str | None]] = []
        self._unreachable = unreachable

    async def send_protected_video(
        self, chat_id: int, file_id: str, caption: str | None = None
    ) -> int:
        if self._unreachable:  # эмулируем «юзер не открыл чат с ботом»
            raise RecipientUnreachableError("chat not found")
        self.sent.append((chat_id, file_id, caption))
        return 1000 + len(self.sent)  # фиктивный message_id отправленного сообщения


class _FakeDeliveries:
    """Фейк VideoDeliveryRepository: копит выданные (user, chat, message)."""

    def __init__(self) -> None:
        self.added: list[tuple[int, int, int]] = []

    async def add(self, user_id: int, chat_id: int, message_id: int) -> None:
        self.added.append((user_id, chat_id, message_id))

    async def list_for_user(self, user_id: int) -> list[VideoDelivery]:
        return [VideoDelivery(c, m) for (u, c, m) in self.added if u == user_id]

    async def clear_for_user(self, user_id: int) -> None:
        self.added = [t for t in self.added if t[0] != user_id]


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
    deliveries = _FakeDeliveries()
    service = PlaybackService(movies, notifier, _OneShotLock(), deliveries)

    outcome = await service.deliver(
        _user(UserStatus.ACTIVE, _NOW + timedelta(days=1)), movie_id=7, now=_NOW
    )

    assert outcome is PlaybackOutcome.DELIVERED
    assert notifier.sent == [(42, "ARCHIVE_FILE_ID", "Фильм")]
    assert movies.play_increments == [7]  # реальная доставка → просмотр засчитан
    # выдача записана (user, chat=личка, message_id) → удалим при истечении подписки
    assert deliveries.added == [(42, 42, 1001)]


async def test_deliver_denies_without_access_and_skips_movie_load() -> None:
    movies = _FakeMovies(_movie())
    notifier = _FakeNotifier()
    deliveries = _FakeDeliveries()
    service = PlaybackService(movies, notifier, _OneShotLock(), deliveries)

    outcome = await service.deliver(
        _user(UserStatus.EXPIRED, _NOW - timedelta(days=1)), movie_id=7, now=_NOW
    )

    assert outcome is PlaybackOutcome.NO_ACCESS
    assert notifier.sent == []
    assert movies.get_calls == []  # без доступа фильм не раскрываем
    assert movies.play_increments == []
    assert deliveries.added == []


async def test_deliver_not_found_when_movie_missing() -> None:
    movies = _FakeMovies(None)
    notifier = _FakeNotifier()
    deliveries = _FakeDeliveries()
    service = PlaybackService(movies, notifier, _OneShotLock(), deliveries)

    outcome = await service.deliver(
        _user(UserStatus.ACTIVE, _NOW + timedelta(days=1)), movie_id=99, now=_NOW
    )

    assert outcome is PlaybackOutcome.NOT_FOUND
    assert notifier.sent == []
    assert movies.play_increments == []
    assert deliveries.added == []


async def test_deliver_reports_bot_blocked_when_recipient_unreachable() -> None:
    """Подписчик не открыл чат с ботом → BOT_BLOCKED (роутер отдаст 409, не 500)."""
    movies = _FakeMovies(_movie())
    notifier = _FakeNotifier(unreachable=True)
    deliveries = _FakeDeliveries()
    service = PlaybackService(movies, notifier, _OneShotLock(), deliveries)

    outcome = await service.deliver(
        _user(UserStatus.ACTIVE, _NOW + timedelta(days=1)), movie_id=7, now=_NOW
    )

    assert outcome is PlaybackOutcome.BOT_BLOCKED
    assert notifier.sent == []  # видео не ушло
    assert movies.play_increments == []  # блок → просмотр не засчитан
    assert deliveries.added == []  # не дошло → нечего удалять потом


async def test_deliver_swallows_rapid_duplicate_send() -> None:
    """Двойной клик «Көру» (тот же юзер+фильм) в окне лока → ОДНА отправка (11.4)."""
    movies = _FakeMovies(_movie())
    notifier = _FakeNotifier()
    deliveries = _FakeDeliveries()
    lock = _OneShotLock()
    service = PlaybackService(movies, notifier, lock, deliveries)
    active = _user(UserStatus.ACTIVE, _NOW + timedelta(days=1))

    first = await service.deliver(active, movie_id=7, now=_NOW)
    second = await service.deliver(active, movie_id=7, now=_NOW)

    assert first is PlaybackOutcome.DELIVERED
    assert second is PlaybackOutcome.DELIVERED  # повтор не ошибка — та же модалка на фронте
    assert notifier.sent == [(42, "ARCHIVE_FILE_ID", "Фильм")]  # но отправка одна
    assert movies.play_increments == [7]  # счётчик +1 один раз (повтор — no-op)
    assert deliveries.added == [(42, 42, 1001)]  # запись выдачи тоже одна (повтор — no-op)
    assert lock.keys == ["send_video:42:7", "send_video:42:7"]
