"""Юнит-тесты FavoriteService на фейке репозитория (без БД).

Проверяем то, ради чего сервис вообще существует поверх репозитория: несуществующий
фильм отсекается ДО записи (иначе внешний ключ дал бы 500 вместо честного 404), а
тумблер звезды идемпотентен — повтор не ошибка.
"""

from __future__ import annotations

from app.application.services.favorite_service import FavoriteService
from app.domain.entities.movie import Movie


def _movie(movie_id: int = 7) -> Movie:
    return Movie(
        id=movie_id,
        title_kk="Фильм",
        description="сипаттама",
        categories=["disney"],
        poster_url="/posters/x.jpg",
        telegram_file_id="FILE",
    )


class _FakeMovies:
    def __init__(self, known: Movie | None) -> None:
        self._known = known

    async def get(self, movie_id: int) -> Movie | None:
        if self._known is not None and self._known.id == movie_id:
            return self._known
        return None


class _FakeFavorites:
    """Фейк репозитория: множество пар (user, movie) + счётчик реальных изменений."""

    def __init__(self) -> None:
        self.rows: set[tuple[int, int]] = set()
        self.changes = 0

    async def add(self, user_id: int, movie_id: int) -> bool:
        if (user_id, movie_id) in self.rows:
            return False
        self.rows.add((user_id, movie_id))
        self.changes += 1
        return True

    async def remove(self, user_id: int, movie_id: int) -> bool:
        if (user_id, movie_id) not in self.rows:
            return False
        self.rows.discard((user_id, movie_id))
        self.changes += 1
        return True

    async def list_for_user(self, user_id: int) -> list[Movie]:
        return [_movie(mid) for (uid, mid) in sorted(self.rows) if uid == user_id]

    async def list_ids(self, user_id: int) -> list[int]:
        return [mid for (uid, mid) in sorted(self.rows) if uid == user_id]


def _service(favorites: _FakeFavorites, movies: _FakeMovies) -> FavoriteService:
    return FavoriteService(favorites, movies)  # type: ignore[arg-type]


async def test_add_rejects_unknown_movie_before_writing() -> None:
    """Несуществующий фильм — 404 от роутера, а не падение на внешнем ключе."""
    favorites = _FakeFavorites()
    service = _service(favorites, _FakeMovies(_movie()))

    assert await service.add(user_id=42, movie_id=999) is False
    assert favorites.rows == set()


async def test_add_is_idempotent() -> None:
    """Повторный тап по звезде ничего не меняет: счётчик популярности не накрутить."""
    favorites = _FakeFavorites()
    service = _service(favorites, _FakeMovies(_movie()))

    assert await service.add(42, 7) is True
    assert await service.add(42, 7) is True  # для юзера — по-прежнему успех
    assert favorites.rows == {(42, 7)}
    assert favorites.changes == 1  # но состояние поменялось ровно один раз


async def test_remove_of_absent_row_is_not_an_error() -> None:
    favorites = _FakeFavorites()
    service = _service(favorites, _FakeMovies(_movie()))

    await service.remove(42, 7)  # не бросает

    assert favorites.rows == set()
    assert favorites.changes == 0


async def test_lists_are_scoped_to_the_user() -> None:
    """Избранное одного человека не видно другому — список строго персональный."""
    favorites = _FakeFavorites()
    service = _service(favorites, _FakeMovies(_movie()))
    await favorites.add(42, 7)
    await favorites.add(99, 8)

    assert await service.list_ids(42) == [7]
    assert [m.id for m in await service.list_for_user(42)] == [7]
