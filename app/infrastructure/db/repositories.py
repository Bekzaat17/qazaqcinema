"""Pg-реализации портов репозиториев (адаптеры). Мапят ORM ↔ домен.

Запись (add/upsert/set_status) коммитит сессию сама — для текущих сценариев
(один запрос = одна транзакция) этого достаточно; при необходимости перейдём на
явный Unit of Work.
"""

from __future__ import annotations

import logging
from collections.abc import Collection
from datetime import date, datetime
from typing import Any, cast

from sqlalchemy import (
    ColumnElement,
    CursorResult,
    Executable,
    delete,
    distinct,
    false,
    func,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.repositories import SortDir, SortField
from app.domain.analytics.events import EventKind
from app.domain.analytics.milestone import Milestone
from app.domain.analytics.report import DailyReport
from app.domain.catalog.popularity import FAVORITE_WEIGHT, PLAY_WEIGHT
from app.domain.entities.delivery import VideoDelivery
from app.domain.entities.enums import PaymentMethod, PaymentStatus, UserStatus
from app.domain.entities.movie import Movie
from app.domain.entities.season import Season
from app.domain.entities.series import Series
from app.domain.entities.subscription import PaymentRequest
from app.domain.entities.user import User
from app.infrastructure.db.models import (
    DailyReportModel,
    FavoriteModel,
    MilestoneModel,
    MovieModel,
    PaymentRequestModel,
    SeasonModel,
    SeriesModel,
    UserEventModel,
    UserModel,
    VideoDeliveryModel,
)

logger = logging.getLogger(__name__)


async def _rowcount(session: AsyncSession, stmt: Executable) -> int:
    """Сколько строк реально задел UPDATE/DELETE/INSERT.

    На этом числе держатся идемпотентность звезды и защита подарка от двойной раздачи:
    «изменили ли мы что-то» — единственный честный ответ от БД, и получить его надо ИЗ
    того же запроса, что менял данные (отдельный SELECT снова открыл бы гонку).

    Приведение типа — здесь, в одном месте: `AsyncSession.execute` объявлен как
    `Result[Any]`, у которого `rowcount` нет; для DML приходит `CursorResult`, у которого
    он есть. Иначе `type: ignore` расползлись бы по всем вызовам.
    """
    result = await session.execute(stmt)
    return cast("CursorResult[Any]", result).rowcount


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


def _user_to_domain(model: UserModel) -> User:
    return User(
        telegram_id=model.telegram_id,
        username=model.username,
        status=UserStatus(model.status),
        expires_at=model.expires_at,
        selected_tariff=model.selected_tariff,
        notifications_enabled=model.notifications_enabled,
        bot_started_at=model.bot_started_at,
        free_view_used_at=model.free_view_used_at,
        free_view_movie_id=model.free_view_movie_id,
    )


def _payment_to_domain(model: PaymentRequestModel) -> PaymentRequest:
    return PaymentRequest(
        id=model.id,
        user_id=model.user_id,
        tariff=model.tariff,
        method=PaymentMethod(model.method),
        status=PaymentStatus(model.status),
        proof_file_id=model.proof_file_id,
        external_charge_id=model.external_charge_id,
        created_at=model.created_at,
        reviewed_at=model.reviewed_at,
    )


def _delivery_to_domain(model: VideoDeliveryModel) -> VideoDelivery:
    return VideoDelivery(
        chat_id=model.chat_id,
        message_id=model.message_id,
        id=model.id,
        attempts=model.attempts,
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

    async def list_popular(self, limit: int) -> list[Movie]:
        """Полка «Танымал»: по баллу популярности, затем рейтингу, затем новизне.

        Балл — просмотры И избранное с весами из `domain/catalog/popularity.py`: просмотр
        доступен только подписчику, поэтому по одним просмотрам полка молчала бы про
        интерес большинства, которое пока не заплатило. Выражение здесь буквально
        повторяет чистую функцию `popularity_score` (она же покрыта тестом без БД).

        Одним ORDER BY покрываем холодный старт: пока оба счётчика по нулям, сортировка
        проваливается на rating (NULLS LAST — без оценки в конец), затем на id.
        """
        score = (
            MovieModel.play_count * PLAY_WEIGHT + MovieModel.favorites_count * FAVORITE_WEIGHT
        )
        stmt = (
            select(MovieModel)
            .order_by(
                score.desc(),
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
    ) -> tuple[list[Movie], int]:
        """Страница каталога: фильтр по категориям (мультивыбор) + сортировка + пагинация.

        `categories` пустой → без фильтра. `sort` — белый список колонок (сырой строки в SQL
        нет). Вторым ключом всегда `id DESC` — стабильный тай-брейк, иначе OFFSET-страницы
        «плывут». Возвращает (страница, total); total тем же фильтром — для has_more/страниц.
        """
        # «views» — честный счётчик просмотров, а НЕ балл популярности: чип в каталоге
        # подписан «Қаралым», и подмешивать туда избранное значило бы врать подписи.
        # Комбинированный балл живёт только на полке «Танымал» (`list_popular`).
        column = {
            "year": MovieModel.year,
            "rating": MovieModel.rating,
            "views": MovieModel.play_count,
        }[sort]
        primary = column.asc() if direction == "asc" else column.desc()
        if sort in ("rating", "year"):
            # год/оценка nullable → фильм без значения уходит в конец при любом направлении.
            primary = primary.nulls_last()
        # тай-брейк id DESC — стабильная страница (год/оценка не уникальны).
        order_by: list[ColumnElement[Any]] = [primary, MovieModel.id.desc()]

        stmt = select(MovieModel)
        count_stmt = select(func.count()).select_from(MovieModel)
        if categories:
            # overlap (`categories && ARRAY[...]`): фильм попадает, если относится ХОТЯ БЫ
            # к одной из выбранных категорий (мультикатегорийность × мультивыбор чипов).
            stmt = stmt.where(MovieModel.categories.overlap(categories))
            count_stmt = count_stmt.where(MovieModel.categories.overlap(categories))
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


class PgUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, telegram_id: int) -> User | None:
        model = await self._session.get(UserModel, telegram_id)
        return _user_to_domain(model) if model else None

    async def upsert(self, user: User) -> User:
        values = {
            "telegram_id": user.telegram_id,
            "username": user.username,
            "status": user.status.value,
            "expires_at": user.expires_at,
            "selected_tariff": user.selected_tariff,
            "notifications_enabled": user.notifications_enabled,
        }
        stmt = pg_insert(UserModel).values(**values)
        # notifications_enabled НЕ в set_ намеренно: upsert (логин/activate/expire/reject)
        # не должен трогать выбор юзера по рассылкам. Менять флаг — только set_notifications
        # (точечный UPDATE). На INSERT нового юзера значение берётся из values (default True).
        # `bot_started_at` — тоже НЕ здесь: это внешний факт (нажал /start / заблокировал
        # бота), а не часть карточки юзера. Попади он в upsert — вход в Mini App затирал бы
        # открытый чат в NULL, и человек снова видел бы кнопку «Ботты ашу».
        # Поля подарка (free_view_*) — по той же причине НЕ здесь ни в values, ни в set_:
        # их проставляет только атомарный `claim_free_view`. Попади они в upsert — активация
        # подписки или отказ модератора обнулили бы уже потраченный подарок, раздав второй.
        stmt = stmt.on_conflict_do_update(
            index_elements=["telegram_id"],
            set_={
                "username": stmt.excluded.username,
                "status": stmt.excluded.status,
                "expires_at": stmt.excluded.expires_at,
                "selected_tariff": stmt.excluded.selected_tariff,
            },
        )
        await self._session.execute(stmt)
        await self._session.commit()
        return user

    async def list_expired(self, now: datetime) -> list[User]:
        stmt = select(UserModel).where(
            UserModel.status == UserStatus.ACTIVE.value,
            UserModel.expires_at.is_not(None),
            UserModel.expires_at < now,
        )
        result = await self._session.scalars(stmt)
        return [_user_to_domain(model) for model in result]

    async def set_bot_started(self, telegram_id: int, at: datetime | None) -> None:
        """Отметить, что чат с ботом открыт (`/start`), либо снять факт при недоставке.

        Одна ручка на оба случая: факт ровно один — «бот может писать этому человеку», —
        и меняют его две стороны, /start и провалившаяся отправка. Точечный UPDATE, а не
        upsert: остальные поля юзера тут ни при чём.
        """
        stmt = (
            update(UserModel)
            .where(UserModel.telegram_id == telegram_id)
            .values(bot_started_at=at)
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def claim_free_view(self, telegram_id: int, movie_id: int, now: datetime) -> bool:
        """Забрать право на подарочный фильм. True — забрали именно мы, False — уже потрачено.

        Ядро защиты от раздачи двух бесплатных фильмов. Проверка и запись — ОДИН
        `UPDATE ... WHERE free_view_used_at IS NULL`: сама СУБД сериализует конкурентов,
        и второй запрос увидит 0 строк. Схема «сначала SELECT, потом UPDATE» здесь не
        годится — два тапа по кнопке на плохой связи прошли бы проверку одновременно.
        """
        stmt = (
            update(UserModel)
            .where(UserModel.telegram_id == telegram_id, UserModel.free_view_used_at.is_(None))
            .values(free_view_used_at=now, free_view_movie_id=movie_id)
        )
        claimed = await _rowcount(self._session, stmt) == 1
        await self._session.commit()
        return claimed

    async def release_free_view(self, telegram_id: int, movie_id: int) -> None:
        """Вернуть право, если подаренное видео так и не дошло (юзер не открыл чат с ботом).

        Без возврата человек терял бы подарок, ни разу его не увидев, — и упирался бы в
        пэйволл, так и не поняв, за что платит. Сверка по `movie_id` обязательна: за время
        неудачной отправки юзер мог успеть забрать подарок другим фильмом, и слепой сброс
        стёр бы уже состоявшийся подарок.
        """
        stmt = (
            update(UserModel)
            .where(UserModel.telegram_id == telegram_id, UserModel.free_view_movie_id == movie_id)
            .values(free_view_used_at=None, free_view_movie_id=None)
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def list_notifiable(self) -> list[int]:
        """telegram_id всех, кто согласен на рассылки о новинках (аудитория Фазы 12).

        Отдаём только id (не полные User) — рассылке больше ничего не нужно, а список
        может быть большим.
        """
        stmt = select(UserModel.telegram_id).where(
            UserModel.notifications_enabled.is_(True)
        )
        result = await self._session.scalars(stmt)
        return list(result)

    async def count_all(self, exclude: Collection[int] = ()) -> int:
        stmt = select(func.count()).select_from(UserModel).where(*_not_in(exclude))
        return int(await self._session.scalar(stmt) or 0)

    async def count_created_since(self, since: datetime, exclude: Collection[int] = ()) -> int:
        stmt = (
            select(func.count())
            .select_from(UserModel)
            .where(UserModel.created_at >= since, *_not_in(exclude))
        )
        return int(await self._session.scalar(stmt) or 0)

    async def count_active(self, now: datetime, exclude: Collection[int] = ()) -> int:
        """Активные подписки ПО ФАКТУ (`expires_at > now`), а не по колонке статуса.

        Статус гасит фоновый джоб раз в 15 минут, поэтому между прогонами ACTIVE-строк
        чуть больше, чем реально доступов. Отчёт должен показывать правду на момент
        отправки — тот же критерий, что и `User.has_active_access`.
        """
        stmt = (
            select(func.count())
            .select_from(UserModel)
            .where(
                UserModel.status == UserStatus.ACTIVE.value,
                UserModel.expires_at.is_not(None),
                UserModel.expires_at > now,
                *_not_in(exclude),
            )
        )
        return int(await self._session.scalar(stmt) or 0)

    async def set_notifications(self, telegram_id: int, enabled: bool) -> None:
        """Точечно переключить флаг рассылок (тумблер в профиле; worker → False при блоке).

        Единственный путь изменения `notifications_enabled` — upsert его сохраняет (см. выше).
        Точечный UPDATE без загрузки строки; несуществующий telegram_id → 0 строк (тихий no-op).
        """
        await self._session.execute(
            update(UserModel)
            .where(UserModel.telegram_id == telegram_id)
            .values(notifications_enabled=enabled)
        )
        await self._session.commit()


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
        added = await _rowcount(self._session, stmt) == 1
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
        removed = await _rowcount(
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


class PgUserEventRepository:
    """Журнал значимых действий. Запись — **fail-open** (деградация в адаптере, как у Redis)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user_id: int, kind: EventKind, meta: str | None = None) -> None:
        try:
            self._session.add(UserEventModel(user_id=user_id, kind=kind.value, meta=meta))
            await self._session.commit()
        except SQLAlchemyError:
            # Статистика не вправе ронять основной сценарий: выданное видео и активная
            # подписка важнее строчки в отчёте. rollback обязателен — после сбоя
            # транзакция Postgres «аварийная», и без него упал бы следующий запрос
            # в этой же сессии, уже по делу.
            logger.warning("Событие %s юзера %s не записано", kind, user_id, exc_info=True)
            await self._session.rollback()

    async def count(self, kind: EventKind, since: datetime, until: datetime) -> int:
        stmt = (
            select(func.count())
            .select_from(UserEventModel)
            .where(*_event_window(kind, since, until))
        )
        return int(await self._session.scalar(stmt) or 0)

    async def count_unique_users(self, kind: EventKind, since: datetime, until: datetime) -> int:
        stmt = select(func.count(distinct(UserEventModel.user_id))).where(
            *_event_window(kind, since, until)
        )
        return int(await self._session.scalar(stmt) or 0)


class PgDailyReportRepository:
    """История снимков (`daily_reports`). Одна операция — upsert по `day`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, report: DailyReport) -> None:
        values = {
            "day": report.day,
            "users_total": report.users_total,
            "users_new": report.users_new,
            "subs_active": report.subs_active,
            "catalog_size": report.catalog_size,
            "opens_total": report.opens_total,
            "opens_unique": report.opens_unique,
            "starts": report.starts,
            "plays": report.plays,
            "free_plays": report.free_plays,
            "daily_plays": report.daily_plays,
            "paywalls": report.paywalls,
            "subscribes": report.subscribes,
            "expires": report.expires,
        }
        stmt = pg_insert(DailyReportModel).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["day"],
            set_={
                **{key: stmt.excluded[key] for key in values if key != "day"},
                # created_at «Core»-апдейт не проходит через ORM onupdate — двигаем явно,
                # чтобы по нему было видно, что снимок за этот день переписан повторно.
                "created_at": func.now(),
            },
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def list_range(self, start: date, end: date) -> list[DailyReport]:
        stmt = (
            select(DailyReportModel)
            .where(DailyReportModel.day >= start, DailyReportModel.day <= end)
            .order_by(DailyReportModel.day)
        )
        result = await self._session.scalars(stmt)
        return [_daily_report_to_domain(model) for model in result]


class PgMilestoneRepository:
    """Лента вех роста (`milestones`). Пишет и читает админ-команда `/milestone`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, label: str, occurred_at: datetime, created_by: int) -> Milestone:
        model = MilestoneModel(label=label, occurred_at=occurred_at, created_by=created_by)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _milestone_to_domain(model)

    async def list_recent(self, limit: int) -> list[Milestone]:
        stmt = select(MilestoneModel).order_by(MilestoneModel.occurred_at.desc()).limit(limit)
        result = await self._session.scalars(stmt)
        return [_milestone_to_domain(model) for model in result]

    async def list_between(self, since: datetime, until: datetime) -> list[Milestone]:
        stmt = (
            select(MilestoneModel)
            .where(MilestoneModel.occurred_at >= since, MilestoneModel.occurred_at < until)
            .order_by(MilestoneModel.occurred_at)
        )
        result = await self._session.scalars(stmt)
        return [_milestone_to_domain(model) for model in result]


def _milestone_to_domain(model: MilestoneModel) -> Milestone:
    return Milestone(
        id=model.id,
        occurred_at=model.occurred_at,
        label=model.label,
        created_by=model.created_by,
    )


def _daily_report_to_domain(model: DailyReportModel) -> DailyReport:
    return DailyReport(
        day=model.day,
        users_total=model.users_total,
        users_new=model.users_new,
        subs_active=model.subs_active,
        catalog_size=model.catalog_size,
        opens_total=model.opens_total,
        opens_unique=model.opens_unique,
        starts=model.starts,
        plays=model.plays,
        free_plays=model.free_plays,
        daily_plays=model.daily_plays,
        paywalls=model.paywalls,
        subscribes=model.subscribes,
        expires=model.expires,
    )


def _not_in(ids: Collection[int]) -> tuple[ColumnElement[bool], ...]:
    """Условие «кроме этих telegram_id» — пустой список не добавляет WHERE вовсе.

    Пустой `NOT IN ()` в SQL невалиден, а `NOT IN (NULL)` вернул бы 0 строк — поэтому
    именно кортеж условий, который разворачивается в `.where(*…)`.
    """
    return (UserModel.telegram_id.notin_(ids),) if ids else ()


def _event_window(
    kind: EventKind, since: datetime, until: datetime
) -> tuple[ColumnElement[bool], ...]:
    """Условие «событие вида kind в полуинтервале [since, until)» — под составной индекс."""
    return (
        UserEventModel.kind == kind.value,
        UserEventModel.created_at >= since,
        UserEventModel.created_at < until,
    )


class PgPaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, request: PaymentRequest) -> PaymentRequest:
        model = PaymentRequestModel(
            user_id=request.user_id,
            tariff=request.tariff,
            method=request.method.value,
            status=request.status.value,
            proof_file_id=request.proof_file_id,
            external_charge_id=request.external_charge_id,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _payment_to_domain(model)

    async def get(self, request_id: int) -> PaymentRequest | None:
        model = await self._session.get(PaymentRequestModel, request_id)
        return _payment_to_domain(model) if model else None

    async def set_status(
        self, request_id: int, status: PaymentStatus, reviewed_at: datetime
    ) -> PaymentRequest | None:
        model = await self._session.get(PaymentRequestModel, request_id)
        if model is None:
            return None
        model.status = status.value
        model.reviewed_at = reviewed_at
        await self._session.commit()
        await self._session.refresh(model)
        return _payment_to_domain(model)


class PgVideoDeliveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user_id: int, chat_id: int, message_id: int) -> None:
        self._session.add(
            VideoDeliveryModel(user_id=user_id, chat_id=chat_id, message_id=message_id)
        )
        await self._session.commit()

    async def list_for_user(self, user_id: int) -> list[VideoDelivery]:
        stmt = select(VideoDeliveryModel).where(VideoDeliveryModel.user_id == user_id)
        result = await self._session.scalars(stmt)
        return [_delivery_to_domain(m) for m in result]

    async def list_due(
        self, older_than: datetime, now: datetime, limit: int
    ) -> list[VideoDelivery]:
        # next_attempt_at IS NULL — строку ещё не пробовали (обычный случай).
        # ORDER BY id — стабильный порядок; разобранная строка либо удаляется, либо
        # получает срок в будущем, поэтому следующий запрос отдаёт другие строки.
        stmt = (
            select(VideoDeliveryModel)
            .where(
                VideoDeliveryModel.created_at < older_than,
                or_(
                    VideoDeliveryModel.next_attempt_at.is_(None),
                    VideoDeliveryModel.next_attempt_at <= now,
                ),
            )
            .order_by(VideoDeliveryModel.id)
            .limit(limit)
        )
        result = await self._session.scalars(stmt)
        return [_delivery_to_domain(m) for m in result]

    async def delete_many(self, ids: list[int]) -> None:
        if not ids:
            return
        await self._session.execute(
            delete(VideoDeliveryModel).where(VideoDeliveryModel.id.in_(ids))
        )
        await self._session.commit()

    async def reschedule(self, ids: list[int], next_attempt_at: datetime) -> None:
        if not ids:
            return
        await self._session.execute(
            update(VideoDeliveryModel)
            .where(VideoDeliveryModel.id.in_(ids))
            .values(
                attempts=VideoDeliveryModel.attempts + 1,
                next_attempt_at=next_attempt_at,
            )
        )
        await self._session.commit()
