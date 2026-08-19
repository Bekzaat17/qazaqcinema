"""Юнит-тесты правила «фильм дня» (`domain/catalog/daily.py`), без БД и сервисов.

Проверяем ровно то, ради чего правило вынесено в домен: стабильность внутри суток
(главная кэшируется и одна на всех — F5 не должен менять бесплатное кино под рукой),
смену в МЕСТНУЮ полночь и отсутствие повторов внутри круга.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from itertools import pairwise

from app.domain.catalog.daily import TZ, day_index, free_until, pick_daily_id

_NOW = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
_POOL = [1, 2, 3, 4, 5]


def test_same_local_day_always_gives_the_same_movie() -> None:
    """Утро и поздний вечер одних местных суток — один и тот же фильм."""
    morning = datetime(2026, 8, 19, 6, 0, tzinfo=TZ)
    night = datetime(2026, 8, 19, 23, 59, tzinfo=TZ)

    assert pick_daily_id(_POOL, morning) == pick_daily_id(_POOL, night)


def test_movie_changes_at_local_midnight_not_utc() -> None:
    """Смена привязана к местной полуночи: 23:00 и 00:30 по Алматы — разные фильмы.

    По UTC оба момента лежат в одних сутках (18:00 и 19:30), и на UTC-границе фильм
    сменился бы в 05:00 утра по Казахстану — посреди ночи, но уже «завтра» на экране.
    """
    before = datetime(2026, 8, 19, 23, 0, tzinfo=TZ)
    after = datetime(2026, 8, 20, 0, 30, tzinfo=TZ)

    assert before.astimezone(UTC).date() == after.astimezone(UTC).date()  # UTC-сутки одни
    assert pick_daily_id(_POOL, before) != pick_daily_id(_POOL, after)


def test_cycle_visits_every_movie_exactly_once() -> None:
    # Встаём на начало круга: произвольное окно попало бы на стык двух перестановок,
    # где повтор законен (это стык, а не «два дня подряд одно и то же»).
    start = _NOW + timedelta(days=-day_index(_NOW) % len(_POOL))

    picks = [pick_daily_id(_POOL, start + timedelta(days=day)) for day in range(len(_POOL))]

    assert sorted(picks) == _POOL  # круг проходит каждый фильм ровно раз
    # Следующий круг — своя перестановка: календарь не превращается в один и тот же цикл.
    next_cycle = [
        pick_daily_id(_POOL, start + timedelta(days=len(_POOL) + day))
        for day in range(len(_POOL))
    ]
    assert sorted(next_cycle) == _POOL


def test_no_repeat_on_consecutive_days_inside_a_cycle() -> None:
    start = _NOW + timedelta(days=-day_index(_NOW) % len(_POOL))
    picks = [pick_daily_id(_POOL, start + timedelta(days=day)) for day in range(len(_POOL))]

    assert all(a != b for a, b in pairwise(picks))


def test_empty_catalog_gives_nothing() -> None:
    assert pick_daily_id([], _NOW) is None


def test_single_movie_catalog_is_stable() -> None:
    """Один фильм в каталоге — он же фильм дня каждый день, без деления на ноль."""
    assert pick_daily_id([7], _NOW) == 7
    assert pick_daily_id([7], _NOW + timedelta(days=1)) == 7


def test_free_until_is_the_next_local_midnight() -> None:
    until = free_until(datetime(2026, 8, 19, 23, 0, tzinfo=TZ))

    assert until == datetime(2026, 8, 20, 0, 0, tzinfo=TZ)
    assert until > _NOW  # таймер на экране всегда положительный
