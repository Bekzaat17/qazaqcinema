from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.domain.analytics.events import EventKind
from app.domain.analytics.report import DailyReport
from app.domain.entities.enums import PaymentMethod, PaymentStatus, UserStatus
from app.domain.entities.movie import Movie
from app.domain.entities.subscription import PaymentRequest
from app.domain.entities.user import User
from app.infrastructure.db.models import DailyReportModel, VideoDeliveryModel
from app.infrastructure.db.repositories import (
    PgDailyReportRepository,
    PgMilestoneRepository,
    PgMovieRepository,
    PgPaymentRepository,
    PgUserEventRepository,
    PgUserRepository,
    PgVideoDeliveryRepository,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


def _movie(title_kk: str, category: str, file_id: str, title_ru: str | None = None) -> Movie:
    return Movie(
        title_kk=title_kk,
        description="описание",
        categories=[category],
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
            categories=["disney"],
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


async def test_movie_search_tolerates_typo_in_short_title(session: AsyncSession) -> None:
    """«шрик» обязан находить «Шрек».

    Триграммной похожести здесь не хватает: similarity('шрек','шрик') = 0.25 при пороге
    0.3 — на коротком слове одна опечатка выбивает сразу два общих триграмма. Ловит
    levenshtein по началу названия.
    """
    repo = PgMovieRepository(session)
    await repo.add(_movie("Шрек", "disney", "f1", title_ru="Шрек"))
    await repo.add(_movie("Наруто", "anime", "f2"))

    assert [m.title_kk for m in await repo.search("шрик")] == ["Шрек"]


async def test_movie_search_typo_works_regardless_of_case(session: AsyncSession) -> None:
    """levenshtein регистр НЕ приводит сам (в отличие от similarity) — снимаем его явно."""
    repo = PgMovieRepository(session)
    await repo.add(_movie("Шрек", "disney", "f1", title_ru="Шрек"))

    assert [m.title_kk for m in await repo.search("ШРИК")] == ["Шрек"]


async def test_movie_search_typo_matches_prefix(session: AsyncSession) -> None:
    """Сравниваем НАЧАЛО названия: «шрик» против всей строки «Шрек 2» дало бы 3 правки."""
    repo = PgMovieRepository(session)
    await repo.add(_movie("Шрек 2", "disney", "f1", title_ru="Шрек 2"))

    assert [m.title_kk for m in await repo.search("шрик")] == ["Шрек 2"]


async def test_movie_search_ignores_typos_in_very_short_queries(session: AsyncSession) -> None:
    """На 1–3 буквах допуск не работает: «кот» иначе притащил бы «кит», «код» и «рот»."""
    repo = PgMovieRepository(session)
    await repo.add(_movie("Кит", "disney", "f1", title_ru="Кит"))

    assert await repo.search("кот") == []


async def test_movie_search_puts_exact_match_above_fuzzy(session: AsyncSession) -> None:
    """Точно набранное — выше исправленного: иначе опечатка перебивала бы прямое попадание."""
    repo = PgMovieRepository(session)
    await repo.add(_movie("Шрик", "disney", "f1", title_ru="Шрик"))   # ровно то, что ввели
    await repo.add(_movie("Шрек", "disney", "f2", title_ru="Шрек"))   # найдено по опечатке

    assert [m.title_kk for m in await repo.search("шрик")] == ["Шрик", "Шрек"]


async def test_movie_search_still_finds_long_title_typos(session: AsyncSession) -> None:
    """Регрессия: старый путь через similarity никуда не делся."""
    repo = PgMovieRepository(session)
    await repo.add(_movie("Гарфилд", "disney", "f1", title_ru="Гарфилд"))

    assert [m.title_kk for m in await repo.search("гарфилт")] == ["Гарфилд"]


async def test_movie_rotation_pool_is_the_whole_catalog_in_stable_order(
    session: AsyncSession,
) -> None:
    """Пул фильма дня — ВЕСЬ каталог, отсортированный по id.

    Фильтра по баннеру тут нет намеренно: hero строится и из постера, а отбор «только с
    баннером» урезал бы пул втрое. Порядок обязан быть стабильным — перестановка круга
    детерминирована, и «плавающая» сортировка меняла бы фильм дня между запросами.
    """
    repo = PgMovieRepository(session)
    with_banner = _movie("Баннері бар", "disney", "f1")
    with_banner.hero_image_url = "/posters/hero1.jpg"
    first = await repo.add(with_banner)
    second = await repo.add(_movie("Баннерсіз", "anime", "f2"))  # hero_image_url = NULL

    assert await repo.list_rotation_ids() == [first.id, second.id]


def _rated(title_kk: str, file_id: str, rating: float | None) -> Movie:
    return Movie(
        title_kk=title_kk,
        description="d",
        categories=["film"],
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
        categories=["anime"], sort="year", direction="desc", limit=10, offset=0
    )
    assert total == 3
    assert all("anime" in m.categories for m in items)

    first, total = await repo.list_page(
        categories=[], sort="year", direction="desc", limit=4, offset=0
    )
    assert total == 8 and len(first) == 4
    second, _ = await repo.list_page(
        categories=[], sort="year", direction="desc", limit=4, offset=4
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


async def test_movie_count_all(session: AsyncSession) -> None:
    """Размер каталога — знаменатель для нормировки метрик отчёта."""
    repo = PgMovieRepository(session)
    assert await repo.count_all() == 0

    await repo.add(_movie("a", "anime", "1"))
    await repo.add(_movie("b", "disney", "2"))

    assert await repo.count_all() == 2


async def test_movie_category_counts(session: AsyncSession) -> None:
    repo = PgMovieRepository(session)
    await repo.add(_movie("a", "anime", "1"))
    await repo.add(_movie("b", "anime", "2"))
    await repo.add(_movie("c", "disney", "3"))

    assert await repo.category_counts() == {"anime": 2, "disney": 1}


async def test_movie_multi_category(session: AsyncSession) -> None:
    """Фильм в нескольких категориях: находится по любой из них, считается в каждой."""
    repo = PgMovieRepository(session)
    await repo.add(
        Movie(
            title_kk="Мұзды өлке",
            description="d",
            categories=["disney", "fantasy", "girls"],
            poster_url="/p.jpg",
            telegram_file_id="f1",
        )
    )
    await repo.add(_movie("Наруто", "anime", "f2"))

    # overlap-фильтр: фильм всплывает по КАЖДОЙ своей категории
    for slug in ("disney", "fantasy", "girls"):
        items, total = await repo.list_page(
            categories=[slug], sort="year", direction="desc", limit=10, offset=0
        )
        assert total == 1 and items[0].title_kk == "Мұзды өлке"

    # мультивыбор чипов disney|anime → оба фильма (по одному разу, без дублей)
    items, total = await repo.list_page(
        categories=["disney", "anime"], sort="year", direction="desc", limit=10, offset=0
    )
    assert total == 2

    # каждая категория мультикатегорийного фильма прибавляет +1 к своему счётчику
    assert await repo.category_counts() == {"disney": 1, "fantasy": 1, "girls": 1, "anime": 1}


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


async def test_delivery_list_due_respects_cutoff_and_limit(session: AsyncSession) -> None:
    await PgUserRepository(session).upsert(User(telegram_id=7))
    repo = PgVideoDeliveryRepository(session)
    now = datetime.now(UTC)
    old_a = await _seed_delivery(session, 7, 101, now - timedelta(hours=41))
    old_b = await _seed_delivery(session, 7, 102, now - timedelta(hours=50))
    await _seed_delivery(session, 7, 103, now - timedelta(hours=1))  # свежая — не трогать

    cutoff = now - timedelta(hours=40)
    due = await repo.list_due(cutoff, now, 10)

    assert {d.message_id for d in due} == {101, 102}
    assert {d.id for d in due} == {old_a, old_b}
    assert all(d.attempts == 0 for d in due)  # ещё не пробовали

    # limit режет пачку (ORDER BY id → стабильно первая)
    assert [d.id for d in await repo.list_due(cutoff, now, 1)] == [old_a]


async def test_delivery_reschedule_hides_row_until_due(session: AsyncSession) -> None:
    """Ключевой инвариант: отложенная строка выпадает из list_due до наступления срока.

    Именно это не даёт циклу чистки зациклиться на сбойной пачке и забить голову очереди.
    """
    await PgUserRepository(session).upsert(User(telegram_id=9))
    repo = PgVideoDeliveryRepository(session)
    now = datetime.now(UTC)
    row = await _seed_delivery(session, 9, 301, now - timedelta(hours=41))
    cutoff = now - timedelta(hours=40)

    await repo.reschedule([row], now + timedelta(hours=1))

    assert await repo.list_due(cutoff, now, 10) == []          # срок не подошёл — скрыта
    later = await repo.list_due(cutoff, now + timedelta(hours=2), 10)  # час спустя — видна
    assert [d.id for d in later] == [row]
    assert later[0].attempts == 1                              # попытка засчитана

    await repo.reschedule([], now)  # пустой список — no-op, не падаем


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


# ── Журнал событий и счётчики отчёта (Фаза «фундамент аналитики») ──────────────


async def test_user_counters_ignore_excluded_ids(session: AsyncSession) -> None:
    """Счётчики отчёта: активные — по факту `expires_at > now`, админы — мимо кассы."""
    users = PgUserRepository(session)
    now = datetime.now(UTC)
    await users.upsert(User(telegram_id=1))  # админ
    await users.upsert(
        User(telegram_id=2, status=UserStatus.ACTIVE, expires_at=now + timedelta(days=1))
    )
    # Статус ACTIVE, но срок уже вышел: джоб гашения ходит раз в 15 минут, а отчёт
    # обязан показывать правду на момент отправки — такой юзер активным не считается.
    await users.upsert(
        User(telegram_id=3, status=UserStatus.ACTIVE, expires_at=now - timedelta(minutes=1))
    )

    assert await users.count_all() == 3
    assert await users.count_all(exclude=[1]) == 2
    assert await users.count_active(now) == 1
    assert await users.count_created_since(now - timedelta(minutes=5)) == 3
    assert await users.count_created_since(now + timedelta(minutes=5)) == 0


async def test_user_event_counts_by_kind_and_window(session: AsyncSession) -> None:
    users = PgUserRepository(session)
    await users.upsert(User(telegram_id=1))
    await users.upsert(User(telegram_id=2))
    events = PgUserEventRepository(session)
    now = datetime.now(UTC)

    await events.add(1, EventKind.OPEN)
    await events.add(1, EventKind.OPEN)  # тот же человек — уникальных всё ещё один
    await events.add(2, EventKind.OPEN)
    await events.add(2, EventKind.PLAY, meta="7")

    window = (now - timedelta(minutes=5), now + timedelta(minutes=5))
    assert await events.count(EventKind.OPEN, *window) == 3
    assert await events.count_unique_users(EventKind.OPEN, *window) == 2
    assert await events.count(EventKind.PLAY, *window) == 1
    # За пределами окна не считаем ничего.
    future = (now + timedelta(minutes=5), now + timedelta(hours=1))
    assert await events.count(EventKind.OPEN, *future) == 0


def _report(**overrides: object) -> DailyReport:
    base: dict[str, object] = {
        "day": date(2026, 8, 13),
        "users_total": 10,
        "users_new": 1,
        "subs_active": 2,
        "catalog_size": 5,
        "opens_total": 3,
        "opens_unique": 2,
        "starts": 4,
        "plays": 1,
        "free_plays": 0,
        "daily_plays": 0,
        "paywalls": 1,
        "subscribes": 1,
        "expires": 0,
    }
    base.update(overrides)
    return DailyReport(**base)  # type: ignore[arg-type]


async def test_daily_report_save_is_upsert_by_day(session: AsyncSession) -> None:
    """Повторный прогон отчёта за тот же день перезаписывает строку, не плодит дубликат."""
    repo = PgDailyReportRepository(session)

    await repo.save(_report(catalog_size=5))
    await repo.save(_report(catalog_size=9))  # тот же day=2026-08-13, каталог подрос

    rows = (await session.execute(select(func.count()).select_from(DailyReportModel))).scalar()
    assert rows == 1
    saved = await session.get(DailyReportModel, date(2026, 8, 13))
    assert saved is not None and saved.catalog_size == 9


async def test_milestone_add_and_list_recent(session: AsyncSession) -> None:
    repo = PgMilestoneRepository(session)
    now = datetime.now(UTC)
    await repo.add("Фильм дня іске қосылды", now, created_by=1)
    await repo.add("Сыйлық фильм тоқтатылды", now + timedelta(minutes=1), created_by=1)

    recent = await repo.list_recent(10)

    # Свежее — первым.
    assert [m.label for m in recent] == ["Сыйлық фильм тоқтатылды", "Фильм дня іске қосылды"]
    assert recent[0].created_by == 1
