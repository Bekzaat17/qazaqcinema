from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.entities.enums import PaymentMethod, PaymentStatus, UserStatus
from app.domain.entities.movie import Movie
from app.domain.entities.subscription import PaymentRequest
from app.domain.entities.user import User
from app.infrastructure.db.models import VideoDeliveryModel
from app.infrastructure.db.repositories import (
    PgMovieRepository,
    PgPaymentRepository,
    PgUserRepository,
    PgVideoDeliveryRepository,
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


def _rated(title_kk: str, file_id: str, rating: float | None) -> Movie:
    return Movie(
        title_kk=title_kk,
        description="d",
        category="film",
        poster_url="/p.jpg",
        telegram_file_id=file_id,
        rating=rating,
    )


async def test_movie_list_recent_and_popular(session: AsyncSession) -> None:
    repo = PgMovieRepository(session)
    a = await repo.add(_movie("A", "disney", "f1"))
    b = await repo.add(_movie("B", "anime", "f2"))
    c = await repo.add(_movie("C", "film", "f3"))  # новейший (больший id)

    assert [m.title_kk for m in await repo.list_recent(2)] == ["C", "B"]  # новизна + обрезка

    assert a.id and b.id and c.id
    await repo.increment_play_count(c.id)
    await repo.increment_play_count(c.id)
    await repo.increment_play_count(b.id)

    popular = await repo.list_popular(3)
    assert [m.title_kk for m in popular] == ["C", "B", "A"]  # по просмотрам (C=2,B=1,A=0)
    got = await repo.get(c.id)
    assert got is not None and got.play_count == 2  # счётчик доехал до домена


async def test_movie_list_popular_falls_back_to_rating(session: AsyncSession) -> None:
    repo = PgMovieRepository(session)
    for title, fid, rating in [("Low", "l", 6.0), ("High", "h", 9.0), ("NoRating", "n", None)]:
        await repo.add(_rated(title, fid, rating))

    # просмотров нет у всех → сортировка проваливается на rating (NULLS LAST)
    assert [m.title_kk for m in await repo.list_popular(3)] == ["High", "Low", "NoRating"]


async def test_movie_list_page_filters_and_paginates(session: AsyncSession) -> None:
    repo = PgMovieRepository(session)
    for i in range(5):
        await repo.add(_movie(f"D{i}", "disney", f"d{i}"))
    for i in range(3):
        await repo.add(_movie(f"A{i}", "anime", f"a{i}"))

    items, total = await repo.list_page(
        categories=["anime"], sort="date", direction="desc", limit=10, offset=0
    )
    assert total == 3
    assert all(m.category == "anime" for m in items)

    first, total = await repo.list_page(
        categories=[], sort="date", direction="desc", limit=4, offset=0
    )
    assert total == 8 and len(first) == 4
    second, _ = await repo.list_page(
        categories=[], sort="date", direction="desc", limit=4, offset=4
    )
    assert len(second) == 4
    assert {m.id for m in first}.isdisjoint({m.id for m in second})  # страницы не пересекаются


async def test_movie_list_page_sorts_by_rating_nulls_last(session: AsyncSession) -> None:
    repo = PgMovieRepository(session)
    for title, fid, rating in [("R6", "r6", 6.0), ("R9", "r9", 9.0), ("RN", "rn", None)]:
        await repo.add(_rated(title, fid, rating))

    desc_items, _ = await repo.list_page(
        categories=[], sort="rating", direction="desc", limit=10, offset=0
    )
    assert [m.title_kk for m in desc_items] == ["R9", "R6", "RN"]
    asc_items, _ = await repo.list_page(
        categories=[], sort="rating", direction="asc", limit=10, offset=0
    )
    assert [m.title_kk for m in asc_items] == ["R6", "R9", "RN"]  # без оценки всё равно в конце


async def test_movie_category_counts(session: AsyncSession) -> None:
    repo = PgMovieRepository(session)
    await repo.add(_movie("a", "anime", "1"))
    await repo.add(_movie("b", "anime", "2"))
    await repo.add(_movie("c", "disney", "3"))

    assert await repo.category_counts() == {"anime": 2, "disney": 1}


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


async def _seed_delivery(
    session: AsyncSession, user_id: int, message_id: int, created_at: datetime
) -> int:
    """Выдача с ЯВНЫМ created_at: обычный `add` ставит now() (server_default) и состарить
    запись через него нельзя, а чистка по возрасту — ровно про created_at."""
    row = VideoDeliveryModel(
        user_id=user_id, chat_id=user_id, message_id=message_id, created_at=created_at
    )
    session.add(row)
    await session.commit()
    return row.id


async def test_delivery_list_stale_respects_cutoff_and_limit(session: AsyncSession) -> None:
    await PgUserRepository(session).upsert(User(telegram_id=7))
    repo = PgVideoDeliveryRepository(session)
    now = datetime.now(UTC)
    old_a = await _seed_delivery(session, 7, 101, now - timedelta(hours=41))
    old_b = await _seed_delivery(session, 7, 102, now - timedelta(hours=50))
    await _seed_delivery(session, 7, 103, now - timedelta(hours=1))  # свежая — не трогать

    cutoff = now - timedelta(hours=40)
    stale = await repo.list_stale(cutoff, 10)

    assert {d.message_id for d in stale} == {101, 102}
    assert {d.id for d in stale} == {old_a, old_b}

    # limit режет пачку (ORDER BY id → стабильно первая)
    assert [d.id for d in await repo.list_stale(cutoff, 1)] == [old_a]


async def test_delivery_delete_many_removes_only_given_ids(session: AsyncSession) -> None:
    await PgUserRepository(session).upsert(User(telegram_id=8))
    repo = PgVideoDeliveryRepository(session)
    now = datetime.now(UTC)
    doomed = await _seed_delivery(session, 8, 201, now - timedelta(hours=41))
    kept = await _seed_delivery(session, 8, 202, now - timedelta(hours=41))

    await repo.delete_many([doomed])

    assert [d.id for d in await repo.list_for_user(8)] == [kept]
    await repo.delete_many([])  # пустой список — no-op, не падаем
    assert len(await repo.list_for_user(8)) == 1
