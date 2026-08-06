"""Юнит-тесты чистого правила выбора hero (`domain/catalog/hero.py`), без БД и сервисов.

Проверяем ровно то, ради чего правило вынесено в домен: окно закрепления, ежедневную
смену, детерминированность (кэш главной одна на всех) и отсутствие повторов внутри круга.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.catalog.hero import PIN_DAYS, pick_hero
from app.domain.entities.movie import Movie

_NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


def _movie(mid: int, *, created_at: datetime | None = None) -> Movie:
    return Movie(
        id=mid,
        title_kk=f"M{mid}",
        description="d",
        categories=["disney"],
        poster_url="/p.jpg",
        telegram_file_id="fid",
        hero_image_url=f"/posters/hero{mid}.jpg",
        created_at=created_at,
    )


def test_fresh_pinned_wins_over_rotation() -> None:
    pinned = _movie(9, created_at=_NOW - timedelta(days=PIN_DAYS, hours=-1))  # чуть моложе окна
    assert pick_hero(pinned, [_movie(1), _movie(2)], _NOW) is pinned


def test_pinned_older_than_window_gives_way_to_rotation() -> None:
    pinned = _movie(9, created_at=_NOW - timedelta(days=PIN_DAYS, hours=1))
    rotation = [_movie(1), _movie(2)]

    picked = pick_hero(pinned, rotation, _NOW)

    assert picked in rotation


def test_rotation_is_deterministic_for_the_same_day() -> None:
    rotation = [_movie(mid) for mid in (1, 2, 3, 4, 5)]
    later_same_day = _NOW.replace(hour=23, minute=59)

    assert pick_hero(None, rotation, _NOW) is pick_hero(None, rotation, later_same_day)


def test_rotation_visits_every_banner_once_per_cycle() -> None:
    rotation = [_movie(mid) for mid in (1, 2, 3, 4, 5)]
    # Встаём на начало круга: окно из 5 произвольных дней попало бы на стык двух
    # перестановок, где повтор законен (это стык, а не «одно и то же три дня»).
    start = _NOW + timedelta(days=-_NOW.date().toordinal() % len(rotation))

    ids = [
        movie.id
        for day in range(len(rotation))
        if (movie := pick_hero(None, rotation, start + timedelta(days=day))) is not None
    ]

    assert sorted(ids) == [1, 2, 3, 4, 5]  # круг проходит каждый баннер ровно раз
    # Следующий круг — своя перестановка: календарь не превращается в один и тот же цикл.
    next_cycle = [
        movie.id
        for day in range(len(rotation))
        if (movie := pick_hero(None, rotation, start + timedelta(days=len(rotation) + day)))
        is not None
    ]
    assert sorted(next_cycle) == [1, 2, 3, 4, 5]


def test_empty_rotation_keeps_pinned() -> None:
    pinned = _movie(9, created_at=_NOW - timedelta(days=365))
    assert pick_hero(pinned, [], _NOW) is pinned


def test_no_pinned_and_no_rotation_gives_nothing() -> None:
    assert pick_hero(None, [], _NOW) is None


def test_naive_created_at_does_not_explode() -> None:
    """Наивная дата (фикстуры/старые данные) не должна ронять главную TypeError'ом."""
    pinned = _movie(9, created_at=datetime(2026, 8, 6, 11, 0))
    assert pick_hero(pinned, [_movie(1)], _NOW) is pinned
