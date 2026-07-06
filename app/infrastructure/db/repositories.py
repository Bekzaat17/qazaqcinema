"""Pg-реализации портов репозиториев (адаптеры). Мапят ORM ↔ домен.

Запись (add/upsert/set_status) коммитит сессию сама — для текущих сценариев
(один запрос = одна транзакция) этого достаточно; при необходимости перейдём на
явный Unit of Work.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.repositories import SortDir, SortField
from app.domain.entities.enums import PaymentMethod, PaymentStatus, UserStatus
from app.domain.entities.movie import Movie
from app.domain.entities.subscription import PaymentRequest
from app.domain.entities.user import User
from app.infrastructure.db.models import MovieModel, PaymentRequestModel, UserModel


def _movie_to_domain(model: MovieModel) -> Movie:
    return Movie(
        id=model.id,
        title_kk=model.title_kk,
        title_ru=model.title_ru,
        title_original=model.title_original,
        description=model.description,
        category=model.category,
        poster_url=model.poster_url,
        telegram_file_id=model.telegram_file_id,
        year=model.year,
        rating=model.rating,
        is_featured=model.is_featured,
        hero_image_url=model.hero_image_url,
        play_count=model.play_count,
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


class PgMovieRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, movie: Movie) -> Movie:
        model = MovieModel(
            title_kk=movie.title_kk,
            title_ru=movie.title_ru,
            title_original=movie.title_original,
            description=movie.description,
            category=movie.category,
            poster_url=movie.poster_url,
            telegram_file_id=movie.telegram_file_id,
            year=movie.year,
            rating=movie.rating,
            is_featured=movie.is_featured,
            hero_image_url=movie.hero_image_url,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _movie_to_domain(model)

    async def get(self, movie_id: int) -> Movie | None:
        model = await self._session.get(MovieModel, movie_id)
        return _movie_to_domain(model) if model else None

    async def get_hero(self) -> Movie | None:
        """Фильм для hero главной: свежайший featured; если featured нет — самый новый.

        Одним запросом: `is_featured DESC` поднимает помеченные наверх, `id DESC` берёт
        среди них новейший (или новейший вообще, когда помеченных нет).
        """
        stmt = (
            select(MovieModel)
            .order_by(MovieModel.is_featured.desc(), MovieModel.id.desc())
            .limit(1)
        )
        model = await self._session.scalar(stmt)
        return _movie_to_domain(model) if model else None

    async def list_all(self, category: str | None = None) -> list[Movie]:
        stmt = select(MovieModel).order_by(MovieModel.id.desc())
        if category is not None:
            stmt = stmt.where(MovieModel.category == category)
        result = await self._session.scalars(stmt)
        return [_movie_to_domain(model) for model in result]

    async def search(self, query: str) -> list[Movie]:
        """Поиск по названиям (kk/ru/original) и описанию.

        Нечувствителен к регистру и диакритике (`f_unaccent`), ловит подстроку и
        опечатки (pg_trgm). Подстрочное совпадение по `f_unaccent(col) ILIKE %q%`
        ускоряется GIN-trgm индексом; опечатки добирает `similarity()`. Ранжирование —
        по максимальной похожести среди названий (описание в ранг не входит — шумит).
        """
        normalized = func.f_unaccent(query)
        pattern = func.concat("%", normalized, "%")
        searchable = (
            MovieModel.title_kk,
            MovieModel.title_ru,
            MovieModel.title_original,
            MovieModel.description,
        )
        substring_match = or_(*(func.f_unaccent(col).ilike(pattern) for col in searchable))
        relevance = func.greatest(
            func.similarity(func.f_unaccent(MovieModel.title_kk), normalized),
            func.similarity(func.f_unaccent(MovieModel.title_ru), normalized),
            func.similarity(func.f_unaccent(MovieModel.title_original), normalized),
        )
        stmt = (
            select(MovieModel)
            .where(or_(substring_match, relevance > 0.3))
            .order_by(func.coalesce(relevance, 0.0).desc(), MovieModel.id.desc())
        )
        result = await self._session.scalars(stmt)
        return [_movie_to_domain(model) for model in result]

    async def list_recent(self, limit: int) -> list[Movie]:
        """Последние `limit` фильмов (полка «Жаңа түскен»). Новизна — по убыванию id."""
        stmt = select(MovieModel).order_by(MovieModel.id.desc()).limit(limit)
        result = await self._session.scalars(stmt)
        return [_movie_to_domain(model) for model in result]

    async def list_popular(self, limit: int) -> list[Movie]:
        """Полка «Танымал»: по просмотрам, затем рейтингу, затем новизне.

        Одним ORDER BY покрываем холодный старт: пока просмотров нет (у всех play_count 0),
        сортировка проваливается на rating (NULLS LAST — без оценки в конец), затем на id.
        """
        stmt = (
            select(MovieModel)
            .order_by(
                MovieModel.play_count.desc(),
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
        column = {
            "date": MovieModel.id,
            "rating": MovieModel.rating,
            "views": MovieModel.play_count,
        }[sort]
        primary = column.asc() if direction == "asc" else column.desc()
        if sort == "rating":
            primary = primary.nulls_last()  # без оценки — в конец при любом направлении
        order_by = [primary] if sort == "date" else [primary, MovieModel.id.desc()]

        stmt = select(MovieModel)
        count_stmt = select(func.count()).select_from(MovieModel)
        if categories:
            stmt = stmt.where(MovieModel.category.in_(categories))
            count_stmt = count_stmt.where(MovieModel.category.in_(categories))
        stmt = stmt.order_by(*order_by).limit(limit).offset(offset)

        result = await self._session.scalars(stmt)
        items = [_movie_to_domain(model) for model in result]
        total = await self._session.scalar(count_stmt) or 0
        return items, int(total)

    async def category_counts(self) -> dict[str, int]:
        """Число фильмов по категориям (для чипов каталога — показываем только непустые)."""
        stmt = select(MovieModel.category, func.count()).group_by(MovieModel.category)
        result = await self._session.execute(stmt)
        return {category: int(count) for category, count in result.all()}

    async def increment_play_count(self, movie_id: int) -> None:
        """+1 к счётчику просмотров (после успешной выдачи видео). Точечный UPDATE."""
        await self._session.execute(
            update(MovieModel)
            .where(MovieModel.id == movie_id)
            .values(play_count=MovieModel.play_count + 1)
        )
        await self._session.commit()


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
