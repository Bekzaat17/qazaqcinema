"""Еженедельный дайджест: агрегат из истории `daily_reports` + вехи за период.

Строится ПОВЕРХ уже накопленного (см. «История отчётов + лента вех роста»,
решение 2026-08-28), а не отдельными запросами к `user_events`: дневные снимки уже
несут дневные суммы, а вот `catalog_size`/`users_total`/`subs_active` НЕДЕЛЮ НАЗАД
иначе взять неоткуда — это состояние на момент, а не событие, и движок каталога/
юзеров прошлых остатков не хранит (только текущее значение). Ради этого снимки и
заводились.

Окно — **скользящее** (как `day_window` у дневного отчёта), не календарная неделя
пн–вс: семь дневных снимков подряд без разрывов дают ровно семь суток без дыр,
и день запуска джоба можно двигать свободно.

⚠️ `opens_unique` в сумме за неделю — верхняя граница, не точное число разных людей:
дневной снимок считает уникальных ВНУТРИ своих суток, и человек, заходивший в
понедельник и во вторник, даст +1 в оба дня. Точный недельный охват потребовал бы
отдельного запроса к `user_events` с окном в 7 суток — в этой итерации сознательно
не делаем: цифра уже полезна как «сколько заходов на разных людей», просто не
складывается в «ровно N разных человек за неделю».
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from html import escape

from app.domain.analytics.milestone import Milestone
from app.domain.analytics.percent import change, share
from app.domain.analytics.report import DailyReport


@dataclass(frozen=True, slots=True)
class WeekTotals:
    """Суммы «поточных» метрик за 7 дней — то, что в `DailyReport` не стоковое."""

    users_new: int
    starts: int
    opens_total: int
    opens_unique: int
    plays: int
    free_plays: int
    daily_plays: int
    paywalls: int
    subscribes: int
    expires: int


_ZERO_TOTALS = WeekTotals(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)


@dataclass(frozen=True, slots=True)
class WeeklyReport:
    period_start: date
    period_end: date
    catalog_size: int              # на конец периода (последний снимок)
    catalog_size_prev: int | None  # на конец предыдущего периода; None — истории ещё нет
    users_total: int
    subs_active: int
    subs_active_prev: int | None
    current: WeekTotals
    previous: WeekTotals | None    # None — за предыдущие 7 суток снимков не набралось
    milestones: list[Milestone]    # вехи внутри текущего периода, по возрастанию времени


def week_range(today: date) -> tuple[date, date]:
    """Текущее окно: `today` и 6 суток до него — последние 7 суток включительно."""
    return today - timedelta(days=6), today


def previous_week_range(today: date) -> tuple[date, date]:
    """7 суток, непосредственно предшествующих текущему окну (без разрыва и наложения)."""
    cur_start, _ = week_range(today)
    prev_end = cur_start - timedelta(days=1)
    return prev_end - timedelta(days=6), prev_end


def build_weekly_report(
    today: date,
    current_days: list[DailyReport],
    previous_days: list[DailyReport],
    milestones: list[Milestone],
) -> WeeklyReport:
    """Чистая сборка отчёта из уже прочитанных снимков (запросы — забота сервиса)."""
    period_start, period_end = week_range(today)
    current_days = sorted(current_days, key=lambda r: r.day)
    previous_days = sorted(previous_days, key=lambda r: r.day)
    latest = current_days[-1] if current_days else None
    prev_latest = previous_days[-1] if previous_days else None
    return WeeklyReport(
        period_start=period_start,
        period_end=period_end,
        catalog_size=latest.catalog_size if latest else 0,
        catalog_size_prev=prev_latest.catalog_size if prev_latest else None,
        users_total=latest.users_total if latest else 0,
        subs_active=latest.subs_active if latest else 0,
        subs_active_prev=prev_latest.subs_active if prev_latest else None,
        current=_sum_totals(current_days),
        previous=_sum_totals(previous_days) if previous_days else None,
        milestones=sorted(milestones, key=lambda m: m.occurred_at),
    )


def _sum_totals(rows: list[DailyReport]) -> WeekTotals:
    if not rows:
        return _ZERO_TOTALS
    return WeekTotals(
        users_new=sum(r.users_new for r in rows),
        starts=sum(r.starts for r in rows),
        opens_total=sum(r.opens_total for r in rows),
        opens_unique=sum(r.opens_unique for r in rows),
        plays=sum(r.plays for r in rows),
        free_plays=sum(r.free_plays for r in rows),
        daily_plays=sum(r.daily_plays for r in rows),
        paywalls=sum(r.paywalls for r in rows),
        subscribes=sum(r.subscribes for r in rows),
        expires=sum(r.expires for r in rows),
    )


def render_weekly_report(report: WeeklyReport) -> str:
    """Текст дайджеста для личек админов (HTML-безопасен: числа + наши подписи).

    Метки вех — свободный текст админа, поэтому единственное место, где `escape`
    обязателен: всё остальное в отчёте — цифры и константные подписи.
    """
    cur = report.current
    prev = report.previous
    lines = [
        f"📈 <b>Апталық терең есеп</b> · "
        f"{report.period_start:%d.%m} – {report.period_end:%d.%m.%Y}",
        "———",
        f"🎬 Каталог: {report.catalog_size} фильм"
        f"{_delta_suffix(report.catalog_size, report.catalog_size_prev, 'осы аптада')}",
        f"👥 Барлық қолданушы: {report.users_total}",
        _line("✅", "Белсенді жазылым", report.subs_active, report.subs_active_prev),
        "———",
    ]

    lines.append(
        "Воронка — осы апта (өткен апта, Δ%):"
        if prev is not None
        else "Салыстыру үшін деректер жеткіліксіз — алдағы аптадан бастап пайда болады."
    )

    lines.append(_line("🤖", "/start", cur.starts, prev.starts if prev else None))
    lines.append(_line("📱", "Ашты (рет)", cur.opens_total, prev.opens_total if prev else None))
    lines.append(
        _line(
            "📱", "Ашты (бірегей, күн сайын қосынды)", cur.opens_unique,
            prev.opens_unique if prev else None,
            note=_rate_suffix(share(cur.opens_unique, cur.starts), "starts-тен"),
        )
    )

    per_100_cur = _per_100(cur.opens_unique, report.catalog_size)
    per_100_prev = _per_100(prev.opens_unique, report.catalog_size_prev) if prev else None
    if per_100_cur is not None:
        suffix = f" (өткен аптада {per_100_prev})" if per_100_prev is not None else ""
        lines.append(f"📐 100 фильмге шаққанда: {per_100_cur} адам{suffix}")

    lines.append(_line("▶️", "Жазылым бойынша видео", cur.plays, prev.plays if prev else None))
    lines.append(_line("🎁", "Сыйлық фильм", cur.free_plays, prev.free_plays if prev else None))
    lines.append(_line("📅", "Күн фильмі", cur.daily_plays, prev.daily_plays if prev else None))
    lines.append(_line("🔒", "Пэйволл көрді", cur.paywalls, prev.paywalls if prev else None))
    lines.append(
        _line(
            "💳", "Жазылым қосылды", cur.subscribes, prev.subscribes if prev else None,
            note=_rate_suffix(share(cur.subscribes, cur.paywalls), "конверсия"),
        )
    )
    lines.append(_line("⌛️", "Мерзімі бітті", cur.expires, prev.expires if prev else None))

    if report.milestones:
        lines.append("———")
        lines.append("📍 <b>Осы аптадағы вехалар:</b>")
        lines += [
            f"• {m.occurred_at:%d.%m} — {escape(m.label)}" for m in report.milestones
        ]

    return "\n".join(lines)


def _line(emoji: str, label: str, current: int, previous: int | None, note: str = "") -> str:
    """Строка метрики: `emoji label: current (previous, Δ%)note`."""
    return f"{emoji} {label}: {current}{_prev_suffix(current, previous)}{note}"


def _delta_suffix(current: int, previous: int | None, label: str) -> str:
    """Для стоковых величин (каталог): просто прирост, без % — база может быть мала."""
    if previous is None:
        return ""
    delta = current - previous
    return f" ({delta:+d} {label})" if delta else ""


def _prev_suffix(current: int, previous: int | None) -> str:
    if previous is None:
        return ""
    rate = change(current, previous)
    return f" ({previous}, {rate:+d}%)" if rate is not None else f" ({previous})"


def _rate_suffix(rate: int | None, label: str) -> str:
    return f" — {rate}% {label}" if rate is not None else ""


def _per_100(value: int, base: int | None) -> float | None:
    return round(value * 100 / base, 1) if base else None
