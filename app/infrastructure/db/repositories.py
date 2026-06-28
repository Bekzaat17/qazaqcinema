"""Pg-реализации портов репозиториев (адаптеры). Мапят ORM ↔ домен.

Запись (add/upsert/set_status) коммитит сессию сама — для текущих сценариев
(один запрос = одна транзакция) этого достаточно; при необходимости перейдём на
явный Unit of Work.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

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
        created_at=model.created_at,
    )


def _user_to_domain(model: UserModel) -> User:
    return User(
        telegram_id=model.telegram_id,
        username=model.username,
        status=UserStatus(model.status),
        expires_at=model.expires_at,
        selected_tariff=model.selected_tariff,
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
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _movie_to_domain(model)

    async def get(self, movie_id: int) -> Movie | None:
        model = await self._session.get(MovieModel, movie_id)
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
        }
        stmt = pg_insert(UserModel).values(**values)
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
