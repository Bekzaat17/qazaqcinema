"""Интеграционные тесты избранного и подарочного фильма (настоящий Postgres).

Здесь проверяется то, что фейками не проверишь: поведение счётчика популярности при
накрутке и атомарность захвата подарка на уровне СУБД.
"""

from __future__ import annotations

from datetime import UTC, datetime

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
