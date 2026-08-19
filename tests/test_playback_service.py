"""Юнит-тест PlaybackService на фейках (без БД и aiogram).

Проверяем ядро безопасности: видео уходит ТОЛЬКО подписчику; без доступа фильм даже
не загружается; несуществующий фильм → NOT_FOUND без отправки.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.application.ports.telegram import RecipientUnreachableError
from app.application.services.playback_service import PlaybackOutcome, PlaybackService
from app.domain.analytics.events import EventKind
from app.domain.entities.delivery import VideoDelivery
from app.domain.entities.enums import UserStatus
from app.domain.entities.movie import Movie
from app.domain.entities.user import User

from tests.fakes import FakeEvents

_NOW = datetime(2026, 6, 29, tzinfo=UTC)


def _movie() -> Movie:
    return Movie(
        id=7,
        title_kk="Фильм",
        description="сипаттама",
        categories=["disney"],
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


class _FakeDaily:
    """Фейк «фильма дня»: сегодня бесплатен фильм с этим id (None — бесплатных нет)."""

    def __init__(self, movie_id: int | None = None) -> None:
        self._movie_id = movie_id

    async def today_id(self, now: datetime) -> int | None:
        return self._movie_id


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

    async def list_due(
        self, older_than: object, now: object, limit: int
    ) -> list[VideoDelivery]:
        return []

    async def delete_many(self, ids: list[int]) -> None: ...

    async def reschedule(self, ids: list[int], next_attempt_at: object) -> None: ...


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


class _FakeUsers:
    """Фейк `UserRepository` в части подарочного фильма.

    Держит состояние подарка у себя и повторяет главное свойство настоящего адаптера:
    `claim_free_view` — атомарная проверка-и-запись, поэтому второй захват возвращает
    False, даже если вызывающий держит устаревшую копию `User`.
    """

    def __init__(self, user: User | None = None) -> None:
        self.user = user
        self.claims: list[tuple[int, int]] = []
        self.releases: list[tuple[int, int]] = []
        self.bot_started: list[tuple[int, datetime | None]] = []

    async def get(self, telegram_id: int) -> User | None:
        return self.user

    async def claim_free_view(self, telegram_id: int, movie_id: int, now: datetime) -> bool:
        self.claims.append((telegram_id, movie_id))
        if self.user is None or self.user.free_view_used_at is not None:
            return False
        self.user.free_view_used_at = now
        self.user.free_view_movie_id = movie_id
        return True

    async def set_bot_started(self, telegram_id: int, at: datetime | None) -> None:
        self.bot_started.append((telegram_id, at))
        if self.user is not None:
            self.user.bot_started_at = at

    async def release_free_view(self, telegram_id: int, movie_id: int) -> None:
        self.releases.append((telegram_id, movie_id))
        if self.user is not None and self.user.free_view_movie_id == movie_id:
            self.user.free_view_used_at = None
            self.user.free_view_movie_id = None


def _service(
    movies: _FakeMovies,
    notifier: _FakeNotifier,
    deliveries: _FakeDeliveries,
    *,
    lock: _OneShotLock | None = None,
    users: _FakeUsers | None = None,
    events: FakeEvents | None = None,
    daily: _FakeDaily | None = None,
) -> PlaybackService:
    return PlaybackService(
        movies,  # type: ignore[arg-type]
        notifier,  # type: ignore[arg-type]
        lock or _OneShotLock(),  # type: ignore[arg-type]
        deliveries,  # type: ignore[arg-type]
        events or FakeEvents(),  # type: ignore[arg-type]
        users or _FakeUsers(),  # type: ignore[arg-type]
        daily or _FakeDaily(),  # type: ignore[arg-type]
    )


def _user(status: UserStatus, expires_at: datetime | None) -> User:
    return User(telegram_id=42, status=status, expires_at=expires_at)


def _guest(free_view_movie_id: int | None = None) -> User:
    """Без подписки. `free_view_movie_id` задан → подарок уже потрачен на этот фильм."""
    return User(
        telegram_id=42,
        status=UserStatus.NEW,
        free_view_used_at=_NOW - timedelta(days=1) if free_view_movie_id else None,
        free_view_movie_id=free_view_movie_id,
    )


async def test_deliver_sends_protected_video_for_active_subscriber() -> None:
    movies = _FakeMovies(_movie())
    notifier = _FakeNotifier()
    deliveries = _FakeDeliveries()
    service = _service(movies, notifier, deliveries)

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
    service = _service(movies, notifier, deliveries)

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
    service = _service(movies, notifier, deliveries)

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
    service = _service(movies, notifier, deliveries)

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
    service = _service(movies, notifier, deliveries, lock=lock)
    active = _user(UserStatus.ACTIVE, _NOW + timedelta(days=1))

    first = await service.deliver(active, movie_id=7, now=_NOW)
    second = await service.deliver(active, movie_id=7, now=_NOW)

    assert first is PlaybackOutcome.DELIVERED
    assert second is PlaybackOutcome.DELIVERED  # повтор не ошибка — та же модалка на фронте
    assert notifier.sent == [(42, "ARCHIVE_FILE_ID", "Фильм")]  # но отправка одна
    assert movies.play_increments == [7]  # счётчик +1 один раз (повтор — no-op)
    assert deliveries.added == [(42, 42, 1001)]  # запись выдачи тоже одна (повтор — no-op)
    assert lock.keys == ["send_video:42:7", "send_video:42:7"]


# --- подарочный первый фильм ------------------------------------------------------


async def test_gift_is_delivered_on_explicit_consent() -> None:
    """Без подписки, но подарок цел и юзер согласился → фильм уходит бесплатно."""
    movies, notifier, deliveries = _FakeMovies(_movie()), _FakeNotifier(), _FakeDeliveries()
    guest = _guest()
    users, events = _FakeUsers(guest), FakeEvents()
    service = _service(movies, notifier, deliveries, users=users, events=events)

    outcome = await service.deliver(guest, movie_id=7, now=_NOW, use_free_view=True)

    assert outcome is PlaybackOutcome.GIFT_DELIVERED
    assert notifier.sent == [(42, "ARCHIVE_FILE_ID", "Фильм")]
    assert users.claims == [(42, 7)]
    # Бесплатный просмотр — отдельное событие, иначе он смешался бы с оплаченными и
    # цифра «сколько людей попробовали продукт» пропала бы.
    assert events.kinds_for(42) == [EventKind.FREE_PLAY]


async def test_gift_is_not_spent_without_explicit_consent() -> None:
    """Тот же юзер, но флага согласия нет → пэйволл, право осталось нетронутым.

    Так подарок не сгорает от случайного перехода по deep-link на фильм.
    """
    movies, notifier, deliveries = _FakeMovies(_movie()), _FakeNotifier(), _FakeDeliveries()
    guest = _guest()
    users, events = _FakeUsers(guest), FakeEvents()
    service = _service(movies, notifier, deliveries, users=users, events=events)

    outcome = await service.deliver(guest, movie_id=7, now=_NOW)

    assert outcome is PlaybackOutcome.NO_ACCESS
    assert notifier.sent == []
    assert users.claims == []
    assert guest.can_use_free_view()  # подарок цел
    assert events.kinds_for(42) == [EventKind.PAYWALL]


async def test_gift_covers_only_one_movie() -> None:
    """Подарок потрачен на фильм 7 → другой фильм упирается в пэйволл."""
    movies, notifier, deliveries = _FakeMovies(_movie()), _FakeNotifier(), _FakeDeliveries()
    guest = _guest(free_view_movie_id=7)
    users, events = _FakeUsers(guest), FakeEvents()
    service = _service(movies, notifier, deliveries, users=users, events=events)

    outcome = await service.deliver(guest, movie_id=8, now=_NOW, use_free_view=True)

    assert outcome is PlaybackOutcome.NO_ACCESS
    assert notifier.sent == []
    assert events.kinds_for(42) == [EventKind.PAYWALL]


async def test_gifted_movie_is_redelivered_after_retention_cleanup() -> None:
    """Своё подаренное кино можно запросить снова — мы же сами сносим видео через ~40 ч.

    Согласия тут не требуется: тратить уже нечего, право израсходовано раньше.
    """
    movies, notifier, deliveries = _FakeMovies(_movie()), _FakeNotifier(), _FakeDeliveries()
    guest = _guest(free_view_movie_id=7)
    users, events = _FakeUsers(guest), FakeEvents()
    service = _service(movies, notifier, deliveries, users=users, events=events)

    outcome = await service.deliver(guest, movie_id=7, now=_NOW)

    assert outcome is PlaybackOutcome.GIFT_DELIVERED
    assert notifier.sent == [(42, "ARCHIVE_FILE_ID", "Фильм")]
    assert users.claims == []  # повторно право не забираем
    assert events.kinds_for(42) == [EventKind.FREE_PLAY]


async def test_gift_is_returned_when_delivery_fails() -> None:
    """Юзер не открыл чат с ботом → подарок возвращаем: он его так и не увидел."""
    movies = _FakeMovies(_movie())
    notifier, deliveries = _FakeNotifier(unreachable=True), _FakeDeliveries()
    guest = _guest()
    users = _FakeUsers(guest)
    service = _service(movies, notifier, deliveries, users=users)

    outcome = await service.deliver(guest, movie_id=7, now=_NOW, use_free_view=True)

    assert outcome is PlaybackOutcome.BOT_BLOCKED
    assert users.releases == [(42, 7)]
    assert guest.can_use_free_view()  # право снова доступно
    # И снимаем сам факт открытого чата: раз бот не смог написать, чата фактически нет.
    # Дальше Mini App позовёт человека в бота ДО следующей попытки потратить подарок.
    assert users.bot_started == [(42, None)]
    assert not guest.has_bot_chat()


async def test_lost_claim_race_on_same_movie_is_not_a_paywall() -> None:
    """Гонка двойного тапа: захват проиграл, но подарен ИМЕННО этот фильм → отдаём.

    Так второй тап по кнопке не показывает пэйволл человеку, которому подарок ровно
    сейчас выдали, и не портит метрику воронки ложным отказом.
    """
    movies, notifier, deliveries = _FakeMovies(_movie()), _FakeNotifier(), _FakeDeliveries()
    # Копия у вызывающего устарела (подарок ещё «цел»), а в хранилище он уже потрачен.
    stale = _guest()
    users, events = _FakeUsers(_guest(free_view_movie_id=7)), FakeEvents()
    service = _service(movies, notifier, deliveries, users=users, events=events)

    outcome = await service.deliver(stale, movie_id=7, now=_NOW, use_free_view=True)

    assert outcome is PlaybackOutcome.GIFT_DELIVERED
    assert events.kinds_for(42) == [EventKind.FREE_PLAY]  # пэйволла не было


async def test_subscriber_does_not_spend_the_gift() -> None:
    """У подписчика подарок остаётся нетронутым — пригодится, когда подписка кончится."""
    movies, notifier, deliveries = _FakeMovies(_movie()), _FakeNotifier(), _FakeDeliveries()
    active = _user(UserStatus.ACTIVE, _NOW + timedelta(days=1))
    users, events = _FakeUsers(active), FakeEvents()
    service = _service(movies, notifier, deliveries, users=users, events=events)

    outcome = await service.deliver(active, movie_id=7, now=_NOW, use_free_view=True)

    assert outcome is PlaybackOutcome.DELIVERED
    assert users.claims == []
    assert active.can_use_free_view()
    assert events.kinds_for(42) == [EventKind.PLAY]


async def test_gift_survives_retry_while_the_send_lock_is_still_held() -> None:
    """Регрессия прод-бага: подарок сгорал молча на повторном тапе к недоступному боту.

    Сценарий из живой БД (два юзера остались с потраченным подарком и без видео): первый
    тап забрал право, не достучался до бота и право вернул — но лок отправки остался
    висеть свои секунды. Второй тап успевал перезабрать освободившееся право, упирался в
    занятый лок и получал «видео отправлено», хотя не отправлял ничего. Занятый лок при
    СВЕЖЕМ захвате означает не чужую отправку, а чужой провал: право возвращаем.
    """
    movies = _FakeMovies(_movie())
    notifier, deliveries = _FakeNotifier(unreachable=True), _FakeDeliveries()
    guest = _guest()
    users, events = _FakeUsers(guest), FakeEvents()
    lock = _OneShotLock()
    service = _service(movies, notifier, deliveries, lock=lock, users=users, events=events)

    first = await service.deliver(guest, movie_id=7, now=_NOW, use_free_view=True)
    second = await service.deliver(guest, movie_id=7, now=_NOW, use_free_view=True)

    assert first is PlaybackOutcome.BOT_BLOCKED
    assert second is PlaybackOutcome.BOT_BLOCKED  # не ложное «отправлено»
    assert guest.can_use_free_view()  # главное: подарок цел после обоих тапов
    assert users.claims == [(42, 7), (42, 7)] and users.releases == [(42, 7), (42, 7)]
    assert deliveries.added == [] and events.kinds_for(42) == []  # ни выдачи, ни события


# --- фильм дня ---------------------------------------------------------------

async def test_daily_movie_is_free_for_everyone_without_spending_the_gift() -> None:
    """Hero главной сегодня бесплатен: без подписки, без согласия, подарок остаётся цел.

    Это ядро сделки «фильм дня»: человек нажимает «Тегін көру» на витрине и получает
    кино. Потрать мы тут подарок, человек лишался бы права выбрать СВОЁ кино, просто
    ткнув в то, что мы сами показали крупно на первом экране.
    """
    movies, notifier, deliveries = _FakeMovies(_movie()), _FakeNotifier(), _FakeDeliveries()
    guest = _guest()
    users, events = _FakeUsers(guest), FakeEvents()
    service = _service(
        movies, notifier, deliveries, users=users, events=events, daily=_FakeDaily(7)
    )

    outcome = await service.deliver(guest, movie_id=7, now=_NOW)

    assert outcome is PlaybackOutcome.DAILY_DELIVERED
    assert notifier.sent == [(42, "ARCHIVE_FILE_ID", "Фильм")]
    assert users.claims == []            # подарок не забирали
    assert guest.can_use_free_view()     # и он по-прежнему доступен
    assert events.kinds_for(42) == [EventKind.DAILY_PLAY]  # своя метрика, не free_play


async def test_other_movie_still_hits_the_paywall_on_a_free_day() -> None:
    """Бесплатен ровно ОДИН фильм: сосед по полке по-прежнему за подписку."""
    movies, notifier, deliveries = _FakeMovies(_movie()), _FakeNotifier(), _FakeDeliveries()
    guest = _guest(free_view_movie_id=99)  # подарок уже потрачен на другое кино
    users, events = _FakeUsers(guest), FakeEvents()
    service = _service(
        movies, notifier, deliveries, users=users, events=events, daily=_FakeDaily(7)
    )

    outcome = await service.deliver(guest, movie_id=8, now=_NOW)

    assert outcome is PlaybackOutcome.NO_ACCESS
    assert notifier.sent == []
    assert events.kinds_for(42) == [EventKind.PAYWALL]


async def test_subscriber_watching_the_daily_movie_counts_as_a_paid_view() -> None:
    """У подписчика метрика не превращается в «бесплатный просмотр» из-за витрины.

    Порядок оснований важен: подписка проверяется раньше фильма дня, иначе оплаченный
    спрос уезжал бы в счётчик бесплатных показов, и обе цифры стали бы бесполезны.
    """
    movies, notifier, deliveries = _FakeMovies(_movie()), _FakeNotifier(), _FakeDeliveries()
    active = _user(UserStatus.ACTIVE, _NOW + timedelta(days=1))
    users, events = _FakeUsers(active), FakeEvents()
    service = _service(
        movies, notifier, deliveries, users=users, events=events, daily=_FakeDaily(7)
    )

    outcome = await service.deliver(active, movie_id=7, now=_NOW)

    assert outcome is PlaybackOutcome.DELIVERED
    assert events.kinds_for(42) == [EventKind.PLAY]
