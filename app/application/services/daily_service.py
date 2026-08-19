"""Фильм дня: какой фильм сегодня открыт всем бесплатно.

Тонкая обвязка над чистым правилом (`domain/catalog/daily`): достать пул id, выбрать
детерминированно по местным суткам, вернуть карточку. Отдельным сервисом, а не методом
каталога, потому что ответ нужен ДВУМ разным сценариям и обязан совпадать: витрине
(hero главной) и выдаче видео (`PlaybackService` пускает без подписки именно этот фильм).
Разъедься эти два места — человек увидел бы «Тегін көру» и получил 403.

Поверх ротации есть закреп (`DailyPin`): админ командой `/daily <id>` объявляет
сегодняшним конкретный фильм. Закреп живёт до местной полуночи и исчезает сам — это
разовый жест под новинку или рекламу, а не возврат к ручному курированию главной.
"""

from __future__ import annotations

from datetime import datetime

from app.application.ports.catalog_cache import CatalogCache
from app.application.ports.daily_pin import DailyPin
from app.application.ports.repositories import MovieRepository
from app.domain.catalog.daily import day_index, day_start, free_until, pick_daily_id
from app.domain.entities.movie import Movie


class DailyMovieService:
    def __init__(self, movies: MovieRepository, pin: DailyPin, cache: CatalogCache) -> None:
        self._movies = movies
        self._pin = pin
        self._cache = cache

    async def today_id(self, now: datetime) -> int | None:
        """id сегодняшнего бесплатного фильма: закреп админа, иначе ротация.

        Пул — фильмы, добавленные ДО начала текущих суток. Это не придирка: длина пула
        входит в `divmod`, поэтому загруженная днём новинка меняла бы бесплатное кино
        прямо под руками у зрителя — тот, кто минуту назад видел «Тегін көру», получил
        бы на том же фильме пэйволл. Новинка входит в ротацию со следующего дня.
        """
        pinned = await self._pin.get(day_index(now))
        if pinned is not None:
            return pinned
        ids = await self._movies.list_rotation_ids(day_start(now))
        if not ids:
            # Каталог целиком залит сегодня (первый день жизни или разовая большая
            # заливка) — лучше подвижный фильм дня, чем пустая главная.
            ids = await self._movies.list_rotation_ids()
        return pick_daily_id(ids, now)

    async def today(self, now: datetime) -> Movie | None:
        movie_id = await self.today_id(now)
        return None if movie_id is None else await self._movies.get(movie_id)

    async def pin_today(self, movie_id: int, now: datetime) -> Movie | None:
        """Сделать фильм сегодняшним. None — такого фильма нет (закреп не ставим).

        Кэш главной сбрасываем сразу: иначе новый фильм дня ждал бы истечения TTL, а
        админ, нажавший команду, увидел бы старый экран и решил, что она не сработала.
        """
        movie = await self._movies.get(movie_id)
        if movie is None:
            return None
        remaining = int((free_until(now) - now).total_seconds())
        await self._pin.set(day_index(now), movie_id, remaining)
        await self._cache.invalidate()
        return movie
