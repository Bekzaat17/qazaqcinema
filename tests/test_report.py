"""Юнит-тесты домена отчёта: окно отчёта и текст (без БД, без Telegram).

Окно — скользящие 24 часа до `now`, а не «с местной полуночи»: отчёт уходит вечером,
и фиксированная полночь обрубала бы хвост между отправкой и полуночью — эти события
не попадали бы ни в один отчёт вообще (решение 2026-08-26).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.domain.analytics.report import DailyReport, day_window, render_report
from app.domain.analytics.search import SearchDemand, SearchSummary


def test_day_window_covers_last_24_hours() -> None:
    now = datetime(2026, 8, 13, 17, 0, tzinfo=UTC)

    since, until = day_window(now)

    assert since == now - timedelta(hours=24)
    assert until == now


def test_day_window_excludes_events_before_the_previous_run() -> None:
    now = datetime(2026, 8, 13, 17, 0, tzinfo=UTC)
    since, _ = day_window(now)

    # Событие сразу после предыдущего запуска (= начало окна) — уже в отчёте.
    just_after_previous_run = since + timedelta(seconds=1)
    # А чуть раньше предыдущего запуска — ещё нет, его учёл отчёт днём ранее.
    just_before_previous_run = since - timedelta(seconds=1)

    assert just_after_previous_run >= since
    assert just_before_previous_run < since


def _report(**overrides: object) -> DailyReport:
    base: dict[str, object] = {
        "day": date(2026, 8, 13),
        "users_total": 128,
        "users_new": 5,
        "subs_active": 34,
        "catalog_size": 150,
        "opens_total": 41,
        "opens_unique": 27,
        "starts": 50,
        "plays": 63,
        "free_plays": 12,
        "daily_plays": 8,
        "paywalls": 19,
        "subscribes": 3,
        "expires": 1,
    }
    base.update(overrides)
    return DailyReport(**base)  # type: ignore[arg-type]


def test_render_report_contains_all_numbers() -> None:
    text = render_report(_report())

    assert "13.08.2026" in text
    assert "128" in text and "+5" in text
    assert "34" in text
    assert "150" in text  # размер каталога — знаменатель для нормировки
    assert "27 адам (41 рет)" in text
    assert "63" in text
    # Воронка: два разных крючка (разовый подарок и регулярный фильм дня) и упоры
    # в пэйволл — все цифры на виду, иначе события пишутся в БД, но никто их не читает.
    assert "12" in text and "8" in text and "19" in text


def test_render_report_shows_percent_rates_when_denominator_is_nonzero() -> None:
    text = render_report(_report(starts=50, opens_unique=25, paywalls=20, subscribes=5))

    assert "50%" in text  # opens_unique/starts
    assert "25%" in text  # subscribes/paywalls


def test_render_report_omits_rate_when_denominator_is_zero() -> None:
    text = render_report(_report(starts=0, opens_unique=0, paywalls=0, subscribes=0))

    # Пустой знаменатель — молчим, а не делим на ноль и не врём про «0%».
    assert "%" not in text


# ── блок спроса: «іздеп, таппағаны» ───────────────────────────────────────────
def _demand(**overrides: object) -> SearchSummary:
    base: dict[str, object] = {
        "searches": 40,
        "missing": 12,
        "top": (
            SearchDemand(query="көліктер", hits=7, people=5),
            SearchDemand(query="моана 2", hits=3, people=3),
        ),
    }
    return SearchSummary(**{**base, **overrides})  # type: ignore[arg-type]


def test_report_without_demand_has_no_search_block() -> None:
    """Спрос — необязательный аргумент: отчёт обязан собираться и без живого запроса."""
    text = render_report(_report())

    assert "Іздеу" not in text


def test_report_shows_top_missing_queries_with_hits_and_people() -> None:
    """Очередь на озвучку: что искали, сколько раз и сколько РАЗНЫХ людей.

    `people` рядом с `hits` обязателен — десять попыток одного человека и десять разных
    людей это разный по силе сигнал, а в списке они выглядели бы одинаково.
    """
    text = render_report(_report(), _demand())

    assert "🔎 Іздеу: 40 сұрау, 12 нәтижесіз" in text
    assert "1. көліктер — 7× / 5 адам" in text
    assert "2. моана 2 — 3× / 3 адам" in text


def test_report_escapes_the_search_query() -> None:
    """⚠️ Запрос — текст от человека, а отчёт уходит как HTML: без экранирования поиск
    по «<Шрек>» ломает разметку и отчёт не доставляется вообще."""
    text = render_report(
        _report(), _demand(top=(SearchDemand(query="<шрек>", hits=1, people=1),))
    )

    assert "&lt;шрек&gt;" in text
    assert "<шрек>" not in text


def test_report_says_when_nobody_searched() -> None:
    text = render_report(_report(), _demand(searches=0, missing=0, top=()))

    assert "Іздеу: сұрау болмады" in text


def test_report_without_missing_queries_keeps_the_counters() -> None:
    """Искали и всё нашли — очереди на озвучку нет, но цифра поиска остаётся: по ней
    видно, пользуются ли поиском вообще."""
    text = render_report(_report(), _demand(missing=0, top=()))

    assert "40 сұрау, 0 нәтижесіз" in text
    assert "таппағаны" not in text



# --- блок про канал и недельный выбор -------------------------------------------------


def test_channel_growth_needs_yesterdays_snapshot() -> None:
    """Дельта — производная, её не хранят: считаем из вчерашнего снимка прямо в тексте."""
    today = _report(channel_members=1240)
    yesterday = _report(channel_members=1203)

    assert "📣 Арна: 1240 (+37 тәулікте)" in render_report(today, None, yesterday)
    # Вчерашнего снимка нет — показываем абсолютное число без выдуманного прироста.
    assert "📣 Арна: 1240\n" in render_report(today)


def test_channel_move_shows_joins_and_leaves_separately() -> None:
    """Итог скрывает отток: «пришли 40, ушли 35» и «движения не было» — один и тот же
    «+5». В отчёте должны стоять обе цифры, плюсом и минусом."""
    today = _report(channel_members=1240, channel_joins=40, channel_leaves=35)

    assert "📣 Арна: 1240 (+40 / −35)" in render_report(today, None, _report(channel_members=1235))


def test_channel_move_falls_back_to_snapshot_delta() -> None:
    """За сутки до появления журнала движений (или если апдейты не дошли) честнее показать
    разность снимков, чем нарисовать «+0 / −0» там, где людей просто не считали."""
    text = render_report(_report(channel_members=1240), None, _report(channel_members=1203))

    assert "📣 Арна: 1240 (+37 тәулікте)" in text


def test_unknown_member_count_hides_the_line_entirely() -> None:
    """Telegram не ответил → None. Ноль подписчиков и «мы не знаем» — разные вещи, и
    вторая не имеет права выглядеть как обвал аудитории до нуля."""
    assert "Арна:" not in render_report(_report(channel_members=None))


def test_gate_funnel_is_shown_with_conversion() -> None:
    """Прирост канала сам по себе не доказывает ничего — он мог случиться и без нас.
    Атрибуцию даёт пара «сколько уткнулись в гейт → сколько дошли до фильма»."""
    text = render_report(_report(channel_gates=64, weekly_picks=18, weekly_plays=25))

    assert "🎟 Апталық таңдау: 18 алды, 25 көрді" in text
    assert "жазылуды сұрадық 64 → алды 18 (28%)" in text


def test_funnel_line_is_skipped_without_gates() -> None:
    """Делить на ноль нечего, а строка «0 → 0» ничего не сообщает."""
    text = render_report(_report(channel_gates=0, weekly_picks=3))

    assert "🎟 Апталық таңдау: 3 алды" in text
    assert "жазылуды сұрадық" not in text


def test_legacy_gift_line_is_marked_as_old() -> None:
    """Новым подарок не выдаётся: строка должна стремиться к нулю, и это видно в подписи."""
    assert "🎁 Сыйлық фильм (ескі):" in render_report(_report())
