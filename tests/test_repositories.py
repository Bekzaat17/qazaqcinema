from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.entities.enums import PaymentMethod, PaymentStatus, UserStatus
from app.domain.entities.movie import Movie
from app.domain.entities.subscription import PaymentRequest
from app.domain.entities.user import User
from app.infrastructure.db.repositories import (
    PgMovieRepository,
    PgPaymentRepository,
    PgUserRepository,
)
from sqlalchemy.ext.asyncio import AsyncSession


def _movie(title: str, category: str, file_id: str) -> Movie:
    return Movie(
        title=title,
        description="описание",
        category=category,
        poster_url="https://x/y.jpg",
        telegram_file_id=file_id,
    )


async def test_movie_add_and_get(session: AsyncSession) -> None:
    repo = PgMovieRepository(session)
    saved = await repo.add(
        Movie(
            title="Король Лев",
            description="d",
            category="disney",
            poster_url="u",
            telegram_file_id="fid",
            year=1994,
            rating=8.5,
        )
    )
    assert saved.id is not None

    got = await repo.get(saved.id)
    assert got is not None
    assert got.title == "Король Лев"
    assert got.telegram_file_id == "fid"


async def test_movie_list_and_search(session: AsyncSession) -> None:
    repo = PgMovieRepository(session)
    await repo.add(_movie("Король Лев", "disney", "f1"))
    await repo.add(_movie("Наруто", "anime", "f2"))

    assert len(await repo.list_all()) == 2
    assert len(await repo.list_all("anime")) == 1

    found = await repo.search("король")
    assert len(found) == 1
    assert found[0].title == "Король Лев"


async def test_user_upsert_overwrites(session: AsyncSession) -> None:
    repo = PgUserRepository(session)
    await repo.upsert(User(telegram_id=10, username="neo"))
    await repo.upsert(User(telegram_id=10, username="trinity", status=UserStatus.ACTIVE))

    got = await repo.get(10)
    assert got is not None
    assert got.username == "trinity"
    assert got.status is UserStatus.ACTIVE


async def test_user_list_expired(session: AsyncSession) -> None:
    repo = PgUserRepository(session)
    now = datetime.now(UTC)
    await repo.upsert(
        User(telegram_id=1, status=UserStatus.ACTIVE, expires_at=now - timedelta(days=1))
    )
    await repo.upsert(
        User(telegram_id=2, status=UserStatus.ACTIVE, expires_at=now + timedelta(days=1))
    )

    expired = await repo.list_expired(now)
    assert [user.telegram_id for user in expired] == [1]


async def test_payment_lifecycle(session: AsyncSession) -> None:
    await PgUserRepository(session).upsert(User(telegram_id=5))
    repo = PgPaymentRepository(session)

    created = await repo.add(
        PaymentRequest(
            user_id=5, tariff="1_month", method=PaymentMethod.KASPI, proof_file_id="pf"
        )
    )
    assert created.id is not None
    assert created.status is PaymentStatus.PENDING
    assert created.created_at is not None

    updated = await repo.set_status(created.id, PaymentStatus.APPROVED, datetime.now(UTC))
    assert updated is not None
    assert updated.status is PaymentStatus.APPROVED
    assert updated.reviewed_at is not None
