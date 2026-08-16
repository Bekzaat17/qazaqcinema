"""Use-case «избранное» («Таңдаулы») — личный список фильмов.

К правам доступа отношения НЕ имеет: звёздочку ставит кто угодно, включая человека без
подписки. Это намеренно — избранное часть свободного каталога, по которому люди ходят
до оплаты, и заодно единственный сигнал интереса, который непокупатель вообще может
подать (просмотр ему недоступен). Поэтому же оно участвует в сортировке «Танымал»
(`domain/catalog/popularity.py`).

Сервис тонкий, но не лишний: он проверяет существование фильма ДО записи. Без проверки
несуществующий id упирался бы во внешний ключ и всплывал 500-й вместо честного 404.
"""

from __future__ import annotations

from app.application.ports.repositories import FavoriteRepository, MovieRepository
from app.domain.entities.movie import Movie


class FavoriteService:
    def __init__(self, favorites: FavoriteRepository, movies: MovieRepository) -> None:
        self._favorites = favorites
        self._movies = movies

    async def add(self, user_id: int, movie_id: int) -> bool:
        """Добавить в избранное. False — такого фильма нет (роутер отдаст 404).

        Повторное добавление — не ошибка: кнопка-звезда идемпотентна по смыслу, и на
        дубль-тапе человек должен видеть «в избранном», а не сообщение о сбое.
        """
        if await self._movies.get(movie_id) is None:
            return False
        await self._favorites.add(user_id, movie_id)
        return True

    async def remove(self, user_id: int, movie_id: int) -> None:
        """Убрать из избранного. Отсутствие строки — не ошибка (та же идемпотентность)."""
        await self._favorites.remove(user_id, movie_id)

    async def list_for_user(self, user_id: int) -> list[Movie]:
        """Избранное юзера — свежедобавленные сверху."""
        return await self._favorites.list_for_user(user_id)

    async def list_ids(self, user_id: int) -> list[int]:
        """id избранного — фронт красит ими звёзды в лентах и каталоге."""
        return await self._favorites.list_ids(user_id)
