"""Ежедневный отчёт админам: срез цифр + его текст (чистая функция, без БД и Telegram).

Здесь только домен: что считаем и как это выглядит. Откуда берутся числа — забота
`AnalyticsService`, когда слать — забота планировщика. Поэтому текст отчёта проверяется
юнит-тестом без Postgres, как `pick_daily_id` и `compute_expiry`.

Язык — казахский, как и вся исходящая переписка бота (карточки чеков и обращений).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, tzinfo


@dataclass(frozen=True, slots=True)
class DailyReport:
    """Срез за сутки. `*_total` — накопленные величины, остальное — за отчётный день."""

    day: date
    users_total: int      # всего пользователей в БД (нажавшие /start тоже считаются)
    users_new: int        # из них появились сегодня
    subs_active: int      # активных подписок прямо сейчас
    opens_total: int      # открытий Mini App за день
    opens_unique: int     # ...из них уникальных людей (главная метрика живой аудитории)
    plays: int            # выданных видео за день (по подписке)
    free_plays: int       # ...и отдельно подарочных первых фильмов
    paywalls: int         # упоров в пэйволл: хотел смотреть, но платить пока не стал
    subscribes: int       # активаций/продлений подписки за день
    expires: int          # истёкших подписок за день


def day_window(now: datetime, tz: tzinfo) -> tuple[datetime, datetime]:
    """Границы «сегодня» в часовом поясе `tz`, приведённые к UTC.

    Отчёт уходит в 23:00 по местному времени, а в БД всё лежит в UTC (+5 у Казахстана):
    без пересчёта «сутки» съехали бы на 5 часов и в отчёт попадал бы кусок вчерашнего дня.
    Верхняя граница — `now`, а не полночь: считаем то, что уже произошло.
    """
    local = now.astimezone(tz)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(UTC), now


def render_report(report: DailyReport) -> str:
    """Текст отчёта для личек админов (HTML-безопасен: только цифры и наши подписи)."""
    return (
        f"📊 <b>Күнделікті есеп</b> · {report.day:%d.%m.%Y}\n"
        "———\n"
        f"👥 Барлық қолданушы: {report.users_total} (бүгін +{report.users_new})\n"
        f"✅ Белсенді жазылым: {report.subs_active}\n"
        "———\n"
        f"📱 Кинотеатрды ашты: {report.opens_unique} адам ({report.opens_total} рет)\n"
        f"▶️ Жіберілген видео: {report.plays}\n"
        # Воронка «сначала ценность, потом оплата» — две цифры рядом читаются как
        # соотношение: сколько людей попробовали продукт и сколько упёрлись в оплату.
        f"🎁 Сыйлық фильм: {report.free_plays}\n"
        f"🔒 Пэйволл көрді: {report.paywalls}\n"
        f"💳 Жазылым қосылды: {report.subscribes}\n"
        f"⌛️ Мерзімі бітті: {report.expires}"
    )
