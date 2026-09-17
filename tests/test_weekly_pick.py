"""Недельное окно бесплатного выбора — чистая математика и правила на `User`.

Окно ОБЩЕЕ для всех и меняется в понедельник 00:00 по Алматы. Проверяем именно границу:
она обязана совпадать с границей суток фильма дня и недели контент-плана, иначе «жаңа
апта» в приложении наступит не тогда, когда о ней напишет канал.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.domain.catalog.daily import TZ
from app.domain.entities.enums import UserStatus
from app.domain.entities.user import User
from app.domain.subscription.weekly import week_end, week_start


def _almaty(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> datetime:
    """Местное время Алматы → UTC, как оно приходит в сервис.

    Собираем в местной зоне и переводим, а не вычитаем 5 часов руками: местную полночь
    (а это ровно та граница, которую тут и проверяем) вычитанием не выразить.
    """
    return datetime(year, month, day, hour, minute, tzinfo=TZ).astimezone(UTC)


# ── Границы окна ─────────────────────────────────────────────────────────────


def test_week_key_is_the_local_monday() -> None:
    monday = date(2026, 9, 21)
    for day in range(7):  # с понедельника по воскресенье — ключ один и тот же
        assert week_start(_almaty(2026, 9, 21 + day)) == monday


def test_window_flips_at_local_midnight_not_utc() -> None:
    """Воскресенье 23:59 — ещё прошлая неделя, понедельник 00:00 — уже новая.

    Контейнеры живут в UTC: в этот момент там ещё воскресенье 19:00, и наивная реализация
    открыла бы новый выбор на пять часов позже, чем обещал канал.
    """
    assert week_start(_almaty(2026, 9, 20, 23, 59)) == date(2026, 9, 14)
    assert week_start(_almaty(2026, 9, 21, 0, 0)) == date(2026, 9, 21)


def test_week_end_is_the_next_local_monday_midnight() -> None:
    """Единая точка отсчёта счётчика: считать «қалды» по каждому юзеру не нужно."""
    ends = week_end(_almaty(2026, 9, 23))
    assert ends.date() == date(2026, 9, 28)
    assert (ends.hour, ends.minute) == (0, 0)
    assert week_start(ends) == date(2026, 9, 28)  # конец одной недели = начало следующей


# ── Правила на пользователе ──────────────────────────────────────────────────


def _user(**overrides: object) -> User:
    base: dict[str, object] = {"telegram_id": 42, "status": UserStatus.NEW}
    return User(**(base | overrides))  # type: ignore[arg-type]


def test_never_picked_may_pick() -> None:
    assert _user().can_pick_weekly(_almaty(2026, 9, 23))


def test_pick_is_spent_for_this_week_and_free_again_on_monday() -> None:
    now = _almaty(2026, 9, 23)
    user = _user(weekly_week=week_start(now), weekly_movie_id=7)

    assert not user.can_pick_weekly(now)
    assert user.can_pick_weekly(_almaty(2026, 9, 28))  # следующий понедельник


def test_picked_movie_is_rewatchable_all_week_but_not_after() -> None:
    """Видео из чата мы сносим через ~40 ч, право живёт до конца недели — иначе уборка
    выглядела бы как «дали и отняли»."""
    picked = _almaty(2026, 9, 21)
    user = _user(weekly_week=week_start(picked), weekly_movie_id=7)

    assert user.is_weekly_movie(7, _almaty(2026, 9, 27, 23))  # воскресенье вечером — да
    assert not user.is_weekly_movie(8, _almaty(2026, 9, 21))  # другой фильм — нет
    assert not user.is_weekly_movie(7, _almaty(2026, 9, 28))  # новая неделя — нет


# ── Что об этом узнаёт фронт ─────────────────────────────────────────────────


def test_auth_hides_a_pick_that_belongs_to_a_past_week() -> None:
    """В колонке лежит и позапрошлый выбор. Бейдж «Менің таңдауым» на фильме, право на
    который уже истекло, обещал бы доступ, которого нет."""
    from app.api.schemas.auth import AuthOut

    now = _almaty(2026, 9, 28)  # понедельник, окно уже новое
    stale = _user(weekly_week=date(2026, 9, 21), weekly_movie_id=7)

    out = AuthOut.from_domain(stale, now)

    assert out.weekly_pick_available
    assert out.weekly_movie_id is None
    assert out.week_ends_at is not None and out.week_ends_at.date() == date(2026, 10, 5)


def test_auth_shows_this_weeks_pick() -> None:
    from app.api.schemas.auth import AuthOut

    now = _almaty(2026, 9, 23)
    out = AuthOut.from_domain(_user(weekly_week=week_start(now), weekly_movie_id=7), now)

    assert not out.weekly_pick_available
    assert out.weekly_movie_id == 7
