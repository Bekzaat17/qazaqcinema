"""Интеграционные тесты избранного, подарочного фильма и недельного выбора (Postgres).

Здесь проверяется то, что фейками не проверишь: поведение счётчика популярности при
накрутке и атомарность захвата (подарка и недельного выбора) на уровне СУБД.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.domain.entities.enums import UserStatus
from app.domain.entities.movie import Movie
from app.domain.entities.user import User
from app.infrastructure.db.repositories import (
    PgFavoriteRepository,
    PgMovieRepository,
    PgUserRepository,
)
from sqlalchemy.ext.asyncio import AsyncSession

_NOW = datetime(2026, 8, 17, tzinfo=UTC)


def _movie(title_kk: str, file_id: str) -> Movie:
    return Movie(
        title_kk=title_kk,
        description="описание",
        categories=["disney"],
        poster_url="/posters/x.jpg",
        telegram_file_id=file_id,
    )


async def _seed(session: AsyncSession, user_id: int = 42) -> tuple[int, PgFavoriteRepository]:
    movie = await PgMovieRepository(session).add(_movie("Фильм", "f1"))
    await PgUserRepository(session).upsert(User(telegram_id=user_id))
    assert movie.id is not None
    return movie.id, PgFavoriteRepository(session)


# --- счётчик популярности: накрутить нельзя -----------------------------------------


async def test_star_toggling_returns_the_counter_exactly_where_it_was(
    session: AsyncSession,
) -> None:
    """Снятие звезды отнимает РОВНО столько же, сколько добавило.

    Это защита от накрутки: цикл «добавил-убрал» сколько угодно раз оставляет счётчик
    на месте, поэтому поднять фильм в «Танымал» одной звездой в своих руках невозможно.
    """
    movie_id, favorites = await _seed(session)
    movies = PgMovieRepository(session)

    async def count() -> int:
        movie = await movies.get(movie_id)
        assert movie is not None
        return movie.favorites_count

    assert await count() == 0
    for _ in range(5):
        await favorites.add(42, movie_id)
        assert await count() == 1  # ровно +1
        await favorites.remove(42, movie_id)
        assert await count() == 0  # и ровно −1 обратно, сколько бы циклов ни было


async def test_repeated_add_counts_once(session: AsyncSession) -> None:
    """Серия тапов по звезде без снятия — одна строка и одна единица счётчика."""
    movie_id, favorites = await _seed(session)
    movies = PgMovieRepository(session)

    assert await favorites.add(42, movie_id) is True
    assert await favorites.add(42, movie_id) is False  # повтор состояния не изменил
    assert await favorites.add(42, movie_id) is False

    movie = await movies.get(movie_id)
    assert movie is not None
    assert movie.favorites_count == 1


async def test_remove_of_absent_row_does_not_touch_the_counter(session: AsyncSession) -> None:
    """Снятие несуществующей звезды не уводит счётчик в минус."""
    movie_id, favorites = await _seed(session)
    movies = PgMovieRepository(session)

    assert await favorites.remove(42, movie_id) is False

    movie = await movies.get(movie_id)
    assert movie is not None
    assert movie.favorites_count == 0


async def test_two_users_count_separately(session: AsyncSession) -> None:
    """Разные люди — разные строки: вот так счётчик и растёт честно."""
    movie_id, favorites = await _seed(session)
    await PgUserRepository(session).upsert(User(telegram_id=99))
    movies = PgMovieRepository(session)

    await favorites.add(42, movie_id)
    await favorites.add(99, movie_id)

    movie = await movies.get(movie_id)
    assert movie is not None
    assert movie.favorites_count == 2
    assert await favorites.list_ids(42) == [movie_id]


async def test_popular_shelf_counts_favorites(session: AsyncSession) -> None:
    """Фильм со звёздами обгоняет фильм без них — избранное реально влияет на «Танымал»."""
    movies = PgMovieRepository(session)
    await movies.add(_movie("Без звёзд", "f1"))
    starred = await movies.add(_movie("Со звездой", "f2"))
    await PgUserRepository(session).upsert(User(telegram_id=42))
    favorites = PgFavoriteRepository(session)
    assert starred.id is not None
    await favorites.add(42, starred.id)

    top = await movies.list_popular(limit=2)

    assert top[0].title_kk == "Со звездой"


# --- подарочный фильм: право забирается ровно один раз --------------------------------


async def test_free_view_is_claimed_only_once(session: AsyncSession) -> None:
    """Второй захват возвращает False — второго бесплатного фильма не бывает."""
    movie_id, _ = await _seed(session)
    users = PgUserRepository(session)

    assert await users.claim_free_view(42, movie_id, _NOW) is True
    assert await users.claim_free_view(42, 999, _NOW) is False  # даже на другой фильм

    user = await users.get(42)
    assert user is not None
    assert user.free_view_movie_id == movie_id
    assert not user.can_use_free_view()


async def test_release_returns_the_right_to_the_user(session: AsyncSession) -> None:
    """Возврат права после несостоявшейся доставки — человек не теряет подарок."""
    movie_id, _ = await _seed(session)
    users = PgUserRepository(session)
    await users.claim_free_view(42, movie_id, _NOW)

    await users.release_free_view(42, movie_id)

    user = await users.get(42)
    assert user is not None
    assert user.can_use_free_view()
    assert user.free_view_movie_id is None


async def test_release_ignores_a_different_movie(session: AsyncSession) -> None:
    """Возврат сверяет фильм: чужой id не должен стирать состоявшийся подарок."""
    movie_id, _ = await _seed(session)
    users = PgUserRepository(session)
    await users.claim_free_view(42, movie_id, _NOW)

    await users.release_free_view(42, movie_id + 12345)

    user = await users.get(42)
    assert user is not None
    assert not user.can_use_free_view()  # подарок на месте


async def test_upsert_does_not_reset_the_gift(session: AsyncSession) -> None:
    """Активация подписки/отказ модератора идут через upsert — подарок они не трогают.

    Инвариант ровно как у `notifications_enabled`: попади поля подарка в upsert, любая
    смена статуса выдавала бы человеку второй бесплатный фильм.
    """
    movie_id, _ = await _seed(session)
    users = PgUserRepository(session)
    await users.claim_free_view(42, movie_id, _NOW)

    stale = await users.get(42)
    assert stale is not None
    stale.free_view_used_at = None  # копия в памяти «забыла» про подарок
    stale.free_view_movie_id = None
    await users.upsert(stale)

    user = await users.get(42)
    assert user is not None
    assert not user.can_use_free_view()
    assert user.free_view_movie_id == movie_id


# --- недельный выбор: один фильм на общее окно -----------------------------------------

_WEEK = date(2026, 9, 21)       # понедельник
_NEXT_WEEK = date(2026, 9, 28)


async def _two_movies(session: AsyncSession) -> tuple[int, int]:
    """Пользователь и два фильма: недельному выбору нужен «какой-то другой» для сверок."""
    first, _ = await _seed(session)
    second = await PgMovieRepository(session).add(_movie("Басқа фильм", "f2"))
    assert second.id is not None
    return first, second.id


async def test_weekly_pick_is_claimed_once_per_week(session: AsyncSession) -> None:
    """Второй захват в ту же неделю не проходит, в новую — проходит.

    Ровно это и делает окно общим: право освобождается сменой ключа, без единой записи
    в БД между неделями.
    """
    movie_id, other_id = await _two_movies(session)
    users = PgUserRepository(session)

    assert await users.claim_weekly_pick(42, movie_id, _WEEK) is True
    assert await users.claim_weekly_pick(42, other_id, _WEEK) is False  # даже другой фильм
    assert await users.claim_weekly_pick(42, other_id, _NEXT_WEEK) is True

    user = await users.get(42)
    assert user is not None
    assert (user.weekly_week, user.weekly_movie_id) == (_NEXT_WEEK, other_id)


async def test_first_pick_works_when_column_is_null(session: AsyncSession) -> None:
    """У ни разу не выбиравшего в колонке NULL: обычное `<>` дало бы NULL, и захват
    не прошёл бы НИКОГДА. Условие обязано быть `IS DISTINCT FROM`."""
    movie_id, _ = await _two_movies(session)
    users = PgUserRepository(session)

    before = await users.get(42)
    assert before is not None and before.weekly_week is None
    assert await users.claim_weekly_pick(42, movie_id, _WEEK) is True


async def test_weekly_release_checks_both_movie_and_week(session: AsyncSession) -> None:
    """Возврат после несостоявшейся доставки — и его сверки."""
    movie_id, other_id = await _two_movies(session)
    users = PgUserRepository(session)
    await users.claim_weekly_pick(42, movie_id, _WEEK)

    await users.release_weekly_pick(42, other_id, _WEEK)    # чужой фильм — не трогаем
    await users.release_weekly_pick(42, movie_id, _NEXT_WEEK)  # чужая неделя — тоже
    user = await users.get(42)
    assert user is not None and user.weekly_movie_id == movie_id

    await users.release_weekly_pick(42, movie_id, _WEEK)
    user = await users.get(42)
    assert user is not None
    assert (user.weekly_week, user.weekly_movie_id) == (None, None)


async def test_upsert_does_not_reset_the_weekly_pick(session: AsyncSession) -> None:
    """Тот же инвариант, что у подарка: иначе вход в Mini App выдавал бы выбор заново."""
    movie_id, _ = await _two_movies(session)
    users = PgUserRepository(session)
    await users.claim_weekly_pick(42, movie_id, _WEEK)

    stale = await users.get(42)
    assert stale is not None
    stale.weekly_week = None  # копия в памяти «забыла» про выбор
    stale.weekly_movie_id = None
    await users.upsert(stale)

    user = await users.get(42)
    assert user is not None
    assert (user.weekly_week, user.weekly_movie_id) == (_WEEK, movie_id)


# --- кому уходят недельные напоминания ------------------------------------------------


async def _reminder_user(
    session: AsyncSession,
    telegram_id: int,
    *,
    week: date | None = None,
    status: UserStatus = UserStatus.NEW,
    expires_at: datetime | None = None,
    notifications: bool = True,
    bot_started: bool = True,
) -> None:
    users = PgUserRepository(session)
    await users.upsert(User(telegram_id=telegram_id, status=status, expires_at=expires_at))
    if week is not None:
        await users.claim_weekly_pick(telegram_id, 1, week)
    if bot_started:
        await users.set_bot_started(telegram_id, _NOW)
    if not notifications:
        await users.set_notifications(telegram_id, False)


async def test_monday_audience_is_last_weeks_pickers(session: AsyncSession) -> None:
    """Пишем тем, кто механикой уже пользовался, а не всей базе."""
    await _reminder_user(session, 1, week=_WEEK)              # брал на прошлой неделе
    await _reminder_user(session, 2, week=_NEXT_WEEK)         # брал на другой
    await _reminder_user(session, 3)                          # не брал никогда
    users = PgUserRepository(session)

    assert await users.list_weekly_pickers(_WEEK, _NOW) == [1]


async def test_saturday_audience_skips_those_who_already_picked(session: AsyncSession) -> None:
    """Напоминание «успейте» — только тем, кто на этой неделе выбор ещё не потратил, и
    только среди пользовавшихся им раньше: иначе это рассылка всей базе."""
    await _reminder_user(session, 1, week=_WEEK)        # уже взял на этой неделе
    await _reminder_user(session, 2, week=_NEXT_WEEK)   # брал, но не на этой
    await _reminder_user(session, 3)                    # не брал никогда — не трогаем
    users = PgUserRepository(session)

    assert await users.list_weekly_idle(_WEEK, _WEEK - timedelta(weeks=4), _NOW) == [2]


async def test_reminders_skip_subscribers_muted_and_botless(session: AsyncSession) -> None:
    """Три отсечения разом: подписчику выбор не нужен, отключивший рассылки не просил
    писать, а без открытого чата письмо не дойдёт — worker жёг бы лимиты на отказах."""
    await _reminder_user(
        session, 1, week=_WEEK, status=UserStatus.ACTIVE, expires_at=_NOW + timedelta(days=5)
    )
    await _reminder_user(session, 2, week=_WEEK, notifications=False)
    await _reminder_user(session, 3, week=_WEEK, bot_started=False)
    await _reminder_user(session, 4, week=_WEEK)  # единственный годный адресат
    users = PgUserRepository(session)

    assert await users.list_weekly_pickers(_WEEK, _NOW) == [4]


async def test_expired_subscriber_is_still_reminded(session: AsyncSession) -> None:
    """Истёкшая подписка — не действующая: такому человеку недельный выбор как раз нужен,
    и он же лучший кандидат вернуться."""
    await _reminder_user(
        session, 1, week=_WEEK, status=UserStatus.ACTIVE, expires_at=_NOW - timedelta(days=1)
    )
    users = PgUserRepository(session)

    assert await users.list_weekly_pickers(_WEEK, _NOW) == [1]


async def test_saturday_reminder_forgets_those_who_left_long_ago(session: AsyncSession) -> None:
    """Горизонт обязателен: без него письмо «успейте взять» капало бы каждую субботу вечно
    всякому, кто однажды выбрал фильм и ушёл."""
    await _reminder_user(session, 1, week=_WEEK - timedelta(weeks=2))   # ещё живой
    await _reminder_user(session, 2, week=_WEEK - timedelta(weeks=9))   # ушёл давно
    users = PgUserRepository(session)

    assert await users.list_weekly_idle(_WEEK, _WEEK - timedelta(weeks=4), _NOW) == [1]
