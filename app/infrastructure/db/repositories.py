"""Pg-реализации портов репозиториев (адаптеры). Мапят ORM ↔ домен.

Скелет: структура и сигнатуры заданы, тела — по PLAN (фаза «БД/репозитории»).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.enums import PaymentStatus
from app.domain.entities.movie import Movie
from app.domain.entities.subscription import PaymentRequest
from app.domain.entities.user import User


class PgMovieRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, movie: Movie) -> Movie:
        raise NotImplementedError

    async def get(self, movie_id: int) -> Movie | None:
        raise NotImplementedError

    async def list_all(self, category: str | None = None) -> list[Movie]:
        raise NotImplementedError

    async def search(self, query: str) -> list[Movie]:
        raise NotImplementedError


class PgUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, telegram_id: int) -> User | None:
        raise NotImplementedError

    async def upsert(self, user: User) -> User:
        raise NotImplementedError

    async def list_expired(self, now: datetime) -> list[User]:
        raise NotImplementedError


class PgPaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, request: PaymentRequest) -> PaymentRequest:
        raise NotImplementedError

    async def get(self, request_id: int) -> PaymentRequest | None:
        raise NotImplementedError

    async def set_status(
        self, request_id: int, status: PaymentStatus, reviewed_at: datetime
    ) -> PaymentRequest | None:
        raise NotImplementedError
