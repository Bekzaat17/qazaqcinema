"""Pg-адаптеры витрины: фильмы, сериалы, сезоны, избранное.

В одном модуле, потому что все четыре живут вокруг строк `movies`: избранное двигает
денормализованный счётчик фильма, а серии — это те же фильмы, привязанные к сезону.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, case, delete, false, func, literal, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.repositories import SortDir, SortField
from app.domain.catalog.popularity import FAVORITE_WEIGHT, PLAY_WEIGHT
from app.domain.entities.movie import Movie
from app.domain.entities.season import Season
from app.domain.entities.series import Series
from app.infrastructure.db.models import FavoriteModel, MovieModel, SeasonModel, SeriesModel
from app.infrastructure.db.sql import rowcount


def _movie_to_domain(model: MovieModel) -> Movie:
    return Movie(
        id=model.id,
        title_kk=model.title_kk,
        title_ru=model.title_ru,
        title_original=model.title_original,
        description=model.description,
        categories=list(model.categories),
        poster_url=model.poster_url,
        telegram_file_id=model.telegram_file_id,
        year=model.year,
        rating=model.rating,
        hero_image_url=model.hero_image_url,
        play_count=model.play_count,
        favorites_count=model.favorites_count,
        season_id=model.season_id,
        episode_number=model.episode_number,
        created_at=model.created_at,
    )


def _series_to_domain(model: SeriesModel) -> Series:
    return Series(id=model.id, title_kk=model.title_kk, created_at=model.created_at)


def _season_to_domain(model: SeasonModel) -> Season:
    return Season(
        id=model.id,
        series_id=model.series_id,
        season_number=model.season_number,
        poster_url=model.poster_url,
        title_kk=model.title_kk,
        description=model.description,
        categories=list(model.categories),
        created_at=model.created_at,
    )


class PgMovieRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, movie: Movie) -> Movie:
        model = MovieModel(
            title_kk=movie.title_kk,
            title_ru=movie.title_ru,
            title_original=movie.title_original,
            description=movie.description,
            categories=movie.categories,
            poster_url=movie.poster_url,
            telegram_file_id=movie.telegram_file_id,
            year=movie.year,
            rating=movie.rating,
            hero_image_url=movie.hero_image_url,
            season_id=movie.season_id,
            episode_number=movie.episode_number,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _movie_to_domain(model)

    async def get(self, movie_id: int) -> Movie | None:
        model = await self._session.get(MovieModel, movie_id)
        return _movie_to_domain(model) if model else None

    async def list_rotation_ids(self, created_before: datetime | None = None) -> list[int]:
        """Пул фильма дня: id ВСЕХ фильмов каталога в стабильном порядке.

        Только id, а не строки целиком: выбирать из пула — работа чистой функции
        (`domain/catalog/daily.pick_daily_id`), а карточка нужна ровно одна, и её
        достаёт `get`. На каталоге в тысячи фильмов это по-прежнему один индексный скан
        по первичному ключу, а не выгрузка витрины в память.

        Порядок по id обязателен: перестановка круга детерминирована, и достаточно
        одной «плавающей» сортировки, чтобы фильм дня менялся между запросами внутри
        одних суток. По той же причине есть `created_before`: длина пула входит в
        `divmod`, поэтому фильм, залитый днём, сдвинул бы сегодняшний выбор.
        """
        stmt = select(MovieModel.id).order_by(MovieModel.id)
        if created_before is not None:
            stmt = stmt.where(MovieModel.created_at < created_before)
        result = await self._session.scalars(stmt)
        return list(result)

    async def list_all(self, category: str | None = None) -> list[Movie]:
        stmt = select(MovieModel).order_by(MovieModel.id.desc())
        if category is not None:
            stmt = stmt.where(MovieModel.categories.overlap([category]))
        result = await self._session.scalars(stmt)
        return [_movie_to_domain(model) for model in result]

    # Ниже этой длины опечатки не ищем: на 1–3 буквах «одна правка» превращает запрос
    # почти в любое название (по «кот» с допуском нашлись бы «кит», «код», «рот»).
    _FUZZY_MIN_LEN = 4
    # Допуск в буквах. Ровно 1: две правки на коротком слове снова дают кашу.
    _FUZZY_MAX_EDITS = 1

    async def search(self, query: str) -> list[Movie]:
        """Поиск по названиям (kk/ru/original) и описанию.

        Три уровня, от точного к терпимому — каждый добирает то, что не поймал прошлый:
        1. подстрока (`ILIKE %q%`, ускоряется GIN-trgm индексом) — обычный ввод;
        2. триграммная похожесть (`similarity > 0.3`) — опечатки в ДЛИННЫХ названиях;
        3. расстояние Левенштейна по началу названия — опечатки в КОРОТКИХ.

        Третий уровень нужен, потому что триграммы на коротких словах бессильны:
        similarity('шрек','шрик') = 0.25, то есть ниже порога — «шрик» не находил
        «Шрека» вообще. Сравниваем не всё название с запросом (у «Шрек 2» против
        «шрик» вышло бы 3 правки), а НАЧАЛО названия длиной с запрос: люди набирают
        первые буквы, а не целиком.

        Регистр и диакритика сняты (`lower` + `f_unaccent`): `similarity` приводит
        регистр сам, а `levenshtein` — нет, для него это разные буквы.
        """
        normalized = func.f_unaccent(query)
        pattern = func.concat("%", normalized, "%")
        titles = (MovieModel.title_kk, MovieModel.title_ru, MovieModel.title_original)
        searchable = (*titles, MovieModel.description)

        substring_match = or_(*(func.f_unaccent(col).ilike(pattern) for col in searchable))
        relevance = func.greatest(
            *(func.similarity(func.f_unaccent(col), normalized) for col in titles)
        )

        conditions = [substring_match, relevance > 0.3]
        if len(query) >= self._FUZZY_MIN_LEN:
            folded = func.lower(normalized)
            head = func.least(
                *(
                    func.levenshtein(
                        func.left(func.lower(func.f_unaccent(col)), func.char_length(folded)),
                        folded,
                    )
                    for col in titles
                )
            )
            conditions.append(head <= self._FUZZY_MAX_EDITS)

        stmt = (
            select(MovieModel)
            .where(or_(*conditions))
            # Точно набранное — всегда выше найденного «по похожести»: иначе исправление
            # опечатки перемешивалось бы с прямым попаданием.
            # ⚠️ coalesce обязателен: `title_original` бывает NULL, а `FALSE OR NULL` в SQL
            # даёт NULL (не FALSE) — и `ORDER BY ... DESC` поднял бы такие строки НАВЕРХ,
            # ровно перед точным совпадением. NULL здесь значит «не совпало» → false.
            .order_by(
                func.coalesce(substring_match, false()).desc(),
                func.coalesce(relevance, 0.0).desc(),
                MovieModel.id.desc(),
            )
        )
        result = await self._session.scalars(stmt)
        return [_movie_to_domain(model) for model in result]

    async def list_recent(self, limit: int) -> list[Movie]:
        """Последние `limit` фильмов (полка «Жаңа түскен»). Новизна — по убыванию id."""
        stmt = select(MovieModel).order_by(MovieModel.id.desc()).limit(limit)
        result = await self._session.scalars(stmt)
        return [_movie_to_domain(model) for model in result]

    @staticmethod
    def _popularity() -> ColumnElement[Any]:
        """Балл популярности: просмотры И избранное с весами домена.

        Одно выражение на полку «Танымал» и на страницу-хаб `/catalog/popular` — две
        копии формулы разошлись бы, и «популярное» в двух местах значило бы разное.
        Буквально повторяет чистую `popularity_score` (она покрыта тестом без БД).
        """
        return MovieModel.play_count * PLAY_WEIGHT + MovieModel.favorites_count * FAVORITE_WEIGHT

    async def list_popular(self, limit: int) -> list[Movie]:
        """Полка «Танымал»: по баллу популярности, затем рейтингу, затем новизне.

        Балл — просмотры И избранное с весами из `domain/catalog/popularity.py`: просмотр
        доступен только подписчику, поэтому по одним просмотрам полка молчала бы про
        интерес большинства, которое пока не заплатило. Выражение здесь буквально
        повторяет чистую функцию `popularity_score` (она же покрыта тестом без БД).

        Одним ORDER BY покрываем холодный старт: пока оба счётчика по нулям, сортировка
        проваливается на rating (NULLS LAST — без оценки в конец), затем на id.
        """
        stmt = (
            select(MovieModel)
            .order_by(
                self._popularity().desc(),
                MovieModel.rating.desc().nulls_last(),
                MovieModel.id.desc(),
            )
            .limit(limit)
        )
        result = await self._session.scalars(stmt)
        return [_movie_to_domain(model) for model in result]

    async def list_page(
        self,
        *,
        categories: list[str],
        sort: SortField,
        direction: SortDir,
        limit: int,
        offset: int,
        year: int | None = None,
    ) -> tuple[list[Movie], int]:
        """Страница каталога: фильтры (категории, год) + сортировка + пагинация.

        `categories` пустой → без фильтра. `sort` — белый список колонок (сырой строки в SQL
        нет). Вторым ключом идёт `id DESC` — стабильный тай-брейк, иначе OFFSET-страницы
        «плывут». Возвращает (страница, total); total тем же фильтром — для has_more/страниц.
        """
        # «views» — честный счётчик просмотров, а НЕ балл популярности: чип в каталоге
        # подписан «Қаралым», и подмешивать туда избранное значило бы врать подписи.
        # Комбинированный балл живёт только на полке «Танымал» (`list_popular`).
        column = {
            "year": MovieModel.year,
            "rating": MovieModel.rating,
            "views": MovieModel.play_count,
            # Новизна = id: он монотонный, а `created_at` у строк одной заливки совпадает
            # до секунды — сортировка по нему «плыла» бы между страницами.
            "newest": MovieModel.id,
            "popular": self._popularity(),
        }[sort]
        primary = column.asc() if direction == "asc" else column.desc()
        if sort in ("rating", "year"):
            # год/оценка nullable → фильм без значения уходит в конец при любом направлении.
            primary = primary.nulls_last()
        # Тай-брейк id DESC — стабильная страница (год/оценка не уникальны). Сортировке
        # по новизне он не нужен: она и есть id, а `ORDER BY id, id` — тот же порядок
        # дважды.
        order_by: list[ColumnElement[Any]] = [primary]
        if sort != "newest":
            order_by.append(MovieModel.id.desc())
        if sort == "popular":
            # На холодном старте балл у всех нулевой, и страницы «популярного» стали бы
            # просто каталогом. Оценка вторым ключом даёт осмысленный порядок сразу
            # (NULLS LAST — без оценки в конец), как на полке «Танымал».
            order_by.insert(1, MovieModel.rating.desc().nulls_last())

        stmt = select(MovieModel)
        count_stmt = select(func.count()).select_from(MovieModel)
        if categories:
            # overlap (`categories && ARRAY[...]`): фильм попадает, если относится ХОТЯ БЫ
            # к одной из выбранных категорий (мультикатегорийность × мультивыбор чипов).
            stmt = stmt.where(MovieModel.categories.overlap(categories))
            count_stmt = count_stmt.where(MovieModel.categories.overlap(categories))
        if year is not None:
            stmt = stmt.where(MovieModel.year == year)
            count_stmt = count_stmt.where(MovieModel.year == year)
        stmt = stmt.order_by(*order_by).limit(limit).offset(offset)

        result = await self._session.scalars(stmt)
        items = [_movie_to_domain(model) for model in result]
        total = await self._session.scalar(count_stmt) or 0
        return items, int(total)

    async def category_counts(self) -> dict[str, int]:
        """Число фильмов по категориям (для чипов каталога — показываем только непустые).

        Категории теперь массив → разворачиваем `unnest` в подзапросе и считаем по slug'у:
        фильм с [fantasy, disney] прибавит по +1 к обеим категориям.
        """
        unnested = select(func.unnest(MovieModel.categories).label("slug")).subquery()
        stmt = select(unnested.c.slug, func.count()).group_by(unnested.c.slug)
        result = await self._session.execute(stmt)
        return {slug: int(count) for slug, count in result.all()}

    async def year_counts(self) -> dict[int, int]:
        """Число фильмов по годам выпуска. Строки без года не считаем — страницы у них нет."""
        stmt = (
            select(MovieModel.year, func.count())
            .where(MovieModel.year.is_not(None))
            .group_by(MovieModel.year)
        )
        result = await self._session.execute(stmt)
        return {int(year): int(count) for year, count in result.all()}

    async def list_related(
        self, *, categories: list[str], exclude_id: int, limit: int
    ) -> list[Movie]:
        """Похожие: пересечение категорий считаем В БАЗЕ, а не перебором выгруженной витрины.

        Число общих категорий собирается суммой CASE по категориям ИСХОДНОГО фильма (их
        единицы), а отбор строк делает GIN-индекс через `&&`. Тай-брейк `id DESC` — тот же
        стабильный порядок, что у остальных списков: страница кэшируется и обязана
        отдаваться всем одинаковой.
        """
        shared: ColumnElement[int] = literal(0)
        for slug in categories:
            shared = shared + case((MovieModel.categories.overlap([slug]), 1), else_=0)

        stmt = (
            select(MovieModel)
            .where(MovieModel.categories.overlap(categories), MovieModel.id != exclude_id)
            .order_by(shared.desc(), MovieModel.id.desc())
            .limit(limit)
        )
        result = await self._session.scalars(stmt)
        return [_movie_to_domain(model) for model in result]

    async def increment_play_count(self, movie_id: int) -> None:
        """+1 к счётчику просмотров (после успешной выдачи видео). Точечный UPDATE."""
        await self._session.execute(
            update(MovieModel)
            .where(MovieModel.id == movie_id)
            .values(play_count=MovieModel.play_count + 1)
        )
        await self._session.commit()

    async def list_by_season(self, season_id: int) -> list[Movie]:
        """Серии одного сезона по возрастанию номера — эпизод-лист сериала."""
        stmt = (
            select(MovieModel)
            .where(MovieModel.season_id == season_id)
            .order_by(MovieModel.episode_number.asc())
        )
        result = await self._session.scalars(stmt)
        return [_movie_to_domain(model) for model in result]

    async def count_all(self) -> int:
        stmt = select(func.count()).select_from(MovieModel)
        return int(await self._session.scalar(stmt) or 0)


class PgSeriesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, series: Series) -> Series:
        model = SeriesModel(title_kk=series.title_kk)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _series_to_domain(model)

    async def get(self, series_id: int) -> Series | None:
        model = await self._session.get(SeriesModel, series_id)
        return _series_to_domain(model) if model else None

    async def list_all(self) -> list[Series]:
        stmt = select(SeriesModel).order_by(SeriesModel.title_kk.asc())
        result = await self._session.scalars(stmt)
        return [_series_to_domain(model) for model in result]


class PgSeasonRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, season: Season) -> Season:
        model = SeasonModel(
            series_id=season.series_id,
            season_number=season.season_number,
            poster_url=season.poster_url,
            title_kk=season.title_kk,
            description=season.description,
            categories=season.categories,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _season_to_domain(model)

    async def get(self, season_id: int) -> Season | None:
        model = await self._session.get(SeasonModel, season_id)
        return _season_to_domain(model) if model else None

    async def list_by_series(self, series_id: int) -> list[Season]:
        stmt = (
            select(SeasonModel)
            .where(SeasonModel.series_id == series_id)
            .order_by(SeasonModel.season_number.asc())
        )
        result = await self._session.scalars(stmt)
        return [_season_to_domain(model) for model in result]


class PgFavoriteRepository:
    """Избранное + поддержание денормализованного `movies.favorites_count`.

    Счётчик двигается ТОЛЬКО когда строка реально появилась/исчезла (сверяем `rowcount`):
    повторное нажатие звезды — не «ещё +1», а no-op, иначе один человек накрутил бы
    популярность фильма серией тапов.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user_id: int, movie_id: int) -> bool:
        """Добавить в избранное. True — добавили сейчас, False — уже было (идемпотентно)."""
        stmt = (
            pg_insert(FavoriteModel)
            .values(user_id=user_id, movie_id=movie_id)
            # Гонка двойного тапа разрешается самой БД: PK (user_id, movie_id) не даст
            # вставить дубль, а do_nothing превращает это в тихий no-op вместо 500.
            .on_conflict_do_nothing(index_elements=["user_id", "movie_id"])
        )
        added = await rowcount(self._session, stmt) == 1
        if added:
            await self._session.execute(
                update(MovieModel)
                .where(MovieModel.id == movie_id)
                .values(favorites_count=MovieModel.favorites_count + 1)
            )
        await self._session.commit()
        return added

    async def remove(self, user_id: int, movie_id: int) -> bool:
        """Убрать из избранного. True — убрали сейчас, False — и не было."""
        removed = await rowcount(
            self._session,
            delete(FavoriteModel).where(
                FavoriteModel.user_id == user_id, FavoriteModel.movie_id == movie_id
            ),
        ) == 1
        if removed:
            await self._session.execute(
                update(MovieModel)
                .where(MovieModel.id == movie_id)
                # greatest(...,0) — страховка от ухода счётчика в минус, если строки
                # избранного когда-нибудь удалят мимо этого метода (каскад, ручной SQL).
                .values(favorites_count=func.greatest(MovieModel.favorites_count - 1, 0))
            )
        await self._session.commit()
        return removed

    async def list_for_user(self, user_id: int) -> list[Movie]:
        """Избранное юзера, свежедобавленные сверху (порядок вкладки «Таңдаулы»)."""
        stmt = (
            select(MovieModel)
            .join(FavoriteModel, FavoriteModel.movie_id == MovieModel.id)
            .where(FavoriteModel.user_id == user_id)
            .order_by(FavoriteModel.created_at.desc(), MovieModel.id.desc())
        )
        result = await self._session.scalars(stmt)
        return [_movie_to_domain(model) for model in result]

    async def list_ids(self, user_id: int) -> list[int]:
        """Только id избранного — чтобы фронт закрасил звёзды в лентах и каталоге.

        Отдельная лёгкая ручка вместо поля `is_favorite` в карточке фильма: ответы
        каталога кэшируются в Redis ОДНИ НА ВСЕХ, и персональный флаг внутри них показал
        бы одному юзеру избранное другого.
        """
        stmt = select(FavoriteModel.movie_id).where(FavoriteModel.user_id == user_id)
        result = await self._session.scalars(stmt)
        return list(result)
