"""Календарь праздников: правила дат, час поздравления, идемпотентность, полнота контента.

Чистый домен — без БД и Telegram. Даты сверены с официальным календарём Казахстана
(Ана күні — 3-е воскресенье сентября, Әке күні — 3-е воскресенье июня, Тіл күні —
5 қыркүйек), поэтому тест ловит и опечатку в правиле, и «поправку» правила наугад.
"""

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime
from pathlib import Path

import yaml
from app.domain.channel.content.kinds import ContentKind
from app.domain.channel.holidays import (
    HOLIDAYS,
    POST_TIMES,
    Fixed,
    Holiday,
    Lunar,
    NthWeekday,
    holiday_for,
    holiday_slot_key,
    holiday_today,
)

CONTENT = Path(__file__).resolve().parents[1] / "content"


def _at(year: int, month: int, day: int, local_hour: int) -> datetime:
    """Местное (Алматы, UTC+5) время суток в UTC — джобы получают именно aware-UTC."""
    return datetime(year, month, day, local_hour - 5, tzinfo=UTC)


# ── правила дат ───────────────────────────────────────────────────────────────
def test_fixed_date_is_the_same_every_year() -> None:
    assert Fixed(3, 21).date_in(2027) == date(2027, 3, 21)
    assert Fixed(3, 21).date_in(2030) == date(2030, 3, 21)


def test_mothers_day_is_the_third_sunday_of_september() -> None:
    rule = NthWeekday(9, calendar.SUNDAY, 3)
    assert rule.date_in(2026) == date(2026, 9, 20)
    assert rule.date_in(2027) == date(2027, 9, 19)


def test_fathers_day_is_the_third_sunday_of_june() -> None:
    rule = NthWeekday(6, calendar.SUNDAY, 3)
    assert rule.date_in(2025) == date(2025, 6, 15)
    assert rule.date_in(2026) == date(2026, 6, 21)


def test_last_weekday_rule_counts_from_the_end() -> None:
    assert NthWeekday(9, calendar.SUNDAY, -1).date_in(2026) == date(2026, 9, 27)


def test_fifth_weekday_that_does_not_exist_is_no_date() -> None:
    """Правило есть, а такого дня в месяце нет → даты нет (а не 1-е следующего месяца)."""
    assert NthWeekday(9, calendar.SUNDAY, 5).date_in(2026) is None


def test_lunar_holiday_has_no_date_outside_its_table() -> None:
    """Год не заполнен — поздравления НЕ будет.

    Ораза айт и Құрбан айт объявляет ДУМК, и объявленная дата отличается от
    астрономической на день. Промолчать честнее, чем поздравить не в тот день: пост
    видят все подписчики сразу.
    """
    rule = Lunar(((2027, 3, 9),))
    assert rule.date_in(2027) == date(2027, 3, 9)
    assert rule.date_in(2031) is None


# ── какой праздник сегодня и в какой час ──────────────────────────────────────
def test_holiday_today_finds_the_date_and_ignores_ordinary_days() -> None:
    assert holiday_today(_at(2027, 3, 21, 9)) is not None
    assert holiday_today(_at(2027, 3, 25, 9)) is None


def test_greeting_hour_must_match_but_minute_may_slip() -> None:
    """Час сверяем, минуту — нет: misfire-окно джоба должно догнать поздравление внутри
    часа, а не потерять его до следующего года."""
    nauryz = datetime(2027, 3, 21, 4, 40, tzinfo=UTC)  # 09:40 Алматы
    assert holiday_for(nauryz) is not None
    assert holiday_for(_at(2027, 3, 21, 15)) is None  # тот же день, чужой час


def test_new_year_is_greeted_one_minute_after_midnight() -> None:
    new_year = next(h for h in HOLIDAYS if h.slug == "zhana-zhyl")
    assert (new_year.hour, new_year.minute) == (0, 1)
    assert holiday_for(datetime(2026, 12, 31, 19, 1, tzinfo=UTC)) is new_year


def test_slot_key_is_local_date_plus_holiday_slug() -> None:
    """UNIQUE в журнале: рестарт и misfire не дадут второго поздравления."""
    nauryz = next(h for h in HOLIDAYS if h.slug == "nauryz")
    assert holiday_slot_key(nauryz, _at(2027, 3, 21, 9)) == "2027-03-21:holiday-nauryz"


def test_post_times_are_derived_from_the_data_without_duplicates() -> None:
    """«Во сколько поздравлять» — данные: джобов ровно столько, сколько различных времён."""
    assert tuple(sorted({(h.hour, h.minute) for h in HOLIDAYS})) == POST_TIMES
    assert (0, 1) in POST_TIMES and (9, 0) in POST_TIMES


# ── целостность справочника и контента ────────────────────────────────────────
def test_holiday_slugs_are_unique() -> None:
    slugs = [h.slug for h in HOLIDAYS]
    assert len(slugs) == len(set(slugs))


def test_two_holidays_on_one_day_are_greeted_at_different_hours() -> None:
    """Совпадение дат бывает (в 2028-м Ұстаз күні падает на Қарттар күні) — и тогда
    поздравления идут оба. Один час у них означал бы, что второе молча пропало: джоб
    возвращает ровно один праздник на час."""
    for year in range(2026, 2031):
        taken: dict[date, list[Holiday]] = {}
        for holiday in HOLIDAYS:
            when = holiday.when.date_in(year)
            if when is not None:
                taken.setdefault(when, []).append(holiday)
        for when, same_day in taken.items():
            hours = [(h.hour, h.minute) for h in same_day]
            assert len(hours) == len(set(hours)), (
                f"{year}-{when}: {[h.slug for h in same_day]} поздравляются в один час"
            )


def _greetings() -> dict[str, dict[str, object]]:
    raw = yaml.safe_load((CONTENT / "holidays.yaml").read_text(encoding="utf-8"))
    return {entry["slug"]: entry for entry in raw}


def test_every_holiday_has_its_greeting_in_the_pool() -> None:
    """Праздник без текста = молчание в самый заметный день. Ловим до заливки."""
    missing = [h.slug for h in HOLIDAYS if h.slug not in _greetings()]
    assert not missing, f"нет поздравлений: {missing}"


def test_greetings_are_greeting_kind_with_text_and_picture() -> None:
    for slug, entry in _greetings().items():
        assert entry["kind"] == ContentKind.GREETING.value, slug
        assert entry["topic"] == "meiram", slug
        assert entry["title"] and entry["body"], slug
        assert entry.get("image") or entry.get("card"), slug


def test_greeting_captions_fit_the_photo_limit() -> None:
    """Подпись к фото — 1024 символа: длинный текст Telegram обрежет молча."""
    for slug, entry in _greetings().items():
        caption = f"{entry['title']}\n\n{entry['body']}"
        assert len(caption) <= 900, f"{slug}: подпись {len(caption)} символов"


def test_picture_credit_is_present_for_every_photo() -> None:
    """Фото с Commons требует указания автора и лицензии — оно печатается в подвале."""
    for slug, entry in _greetings().items():
        if entry.get("image"):
            assert entry.get("image_credit"), slug


def test_holidays_are_listed_in_calendar_order() -> None:
    """Порядок в кортеже — это ещё и приоритет при совпадении дат, поэтому он осмысленный:
    сначала январь, потом декабрь."""
    fixed = [h for h in HOLIDAYS if isinstance(h.when, Fixed)]
    assert fixed == sorted(fixed, key=lambda h: (h.when.month, h.when.day))  # type: ignore[union-attr]


def test_holiday_is_data_not_code() -> None:
    """Новый праздник — строка в справочнике: у `Holiday` нет ни одного метода-поведения."""
    holiday = Holiday("test", "Тест", Fixed(2, 14))
    assert holiday.when.date_in(2027) == date(2027, 2, 14)
    assert (holiday.hour, holiday.minute) == (9, 0)
