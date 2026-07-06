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


def _movie(title_kk: str, category: str, file_id: str, title_ru: str | None = None) -> Movie:
    return Movie(
        title_kk=title_kk,
        description="описание",
        category=category,
        poster_url="/posters/x.jpg",
        telegram_file_id=file_id,
        title_ru=title_ru,
    )


async def test_movie_add_and_get(session: AsyncSession) -> None:
    repo = PgMovieRepository(session)
    saved = await repo.add(
        Movie(
            title_kk="Арыстан Патша",
            title_ru="Король Лев",
            description="d",
            category="disney",
            poster_url="/posters/u.jpg",
            telegram_file_id="fid",
            year=1994,
            rating=8.5,
        )
    )
    assert saved.id is not None
    assert saved.created_at is not None  # проставлен server_default

    got = await repo.get(saved.id)
    assert got is not None
    assert got.title_kk == "Арыстан Патша"
    assert got.title_ru == "Король Лев"
    assert got.telegram_file_id == "fid"


async def test_movie_list_and_search(session: AsyncSession) -> None:
    repo = PgMovieRepository(session)
    await repo.add(_movie("Арыстан Патша", "disney", "f1", title_ru="Король Лев"))
    await repo.add(_movie("Наруто", "anime", "f2"))

    assert len(await repo.list_all()) == 2
    assert len(await repo.list_all("anime")) == 1

    by_ru = await repo.search("король")  # по русскому названию
    assert [m.title_kk for m in by_ru] == ["Арыстан Патша"]

    by_kk = await repo.search("арыстан")  # по казахскому
    assert [m.title_kk for m in by_kk] == ["Арыстан Патша"]

    by_partial = await repo.search("нар")  # частичный ввод
    assert [m.title_kk for m in by_partial] == ["Наруто"]


async def test_movie_get_hero_prefers_featured(session: AsyncSession) -> None:
    repo = PgMovieRepository(session)
    await repo.add(
        Movie(
            title_kk="Басты",
            description="d",
            category="disney",
            poster_url="/p.jpg",
            telegram_file_id="f1",
            is_featured=True,
        )
    )
    await repo.add(_movie("Жаңарақ", "anime", "f2"))  # новее (больший id), но НЕ featured

    hero = await repo.get_hero()
    assert hero is not None
    assert hero.title_kk == "Басты"  # featured побеждает более новый


async def test_movie_get_hero_falls_back_to_newest(session: AsyncSession) -> None:
    repo = PgMovieRepository(session)
    await repo.add(_movie("Ескі", "disney", "f1"))
    await repo.add(_movie("Жаңа", "anime", "f2"))

    hero = await repo.get_hero()
    assert hero is not None
    assert hero.title_kk == "Жаңа"  # featured нет → самый новый (больший id)


async def test_user_upsert_overwrites(session: AsyncSession) -> None:
    repo = PgUserRepository(session)
    await repo.upsert(User(telegram_id=10, username="neo"))
    await repo.upsert(User(telegram_id=10, username="trinity", status=UserStatus.ACTIVE))

    got = await repo.get(10)
    assert got is not None
    assert got.username == "trinity"
    assert got.status is UserStatus.ACTIVE


async def test_user_notifications_default_and_toggle(session: AsyncSession) -> None:
    repo = PgUserRepository(session)
    await repo.upsert(User(telegram_id=1, username="a"))  # notifications_enabled default True
    await repo.upsert(User(telegram_id=2, username="b"))

    assert set(await repo.list_notifiable()) == {1, 2}  # оба по умолчанию в аудитории

    await repo.set_notifications(1, enabled=False)       # тумблер выключил
    assert await repo.list_notifiable() == [2]           # ушёл из аудитории
    got = await repo.get(1)
    assert got is not None and got.notifications_enabled is False


async def test_upsert_preserves_notifications_flag(session: AsyncSession) -> None:
    # Критичный инвариант: upsert (логин/activate/expire/reject) НЕ сбрасывает opt-out.
    repo = PgUserRepository(session)
    await repo.upsert(User(telegram_id=7, username="neo"))
    await repo.set_notifications(7, enabled=False)  # юзер отписался от рассылок

    # повторный upsert с default-True в объекте (напр. смена статуса при оплате)
    await repo.upsert(User(telegram_id=7, username="neo", status=UserStatus.ACTIVE))

    got = await repo.get(7)
    assert got is not None
    assert got.status is UserStatus.ACTIVE           # статус обновился
    assert got.notifications_enabled is False        # но выбор по рассылкам сохранён


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
