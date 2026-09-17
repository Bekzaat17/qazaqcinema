"""Ежедневный отчёт админам: срез цифр + его текст (чистая функция, без БД и Telegram).

Здесь только домен: что считаем и как это выглядит. Откуда берутся числа — забота
`AnalyticsService`, когда слать — забота планировщика. Поэтому текст отчёта проверяется
юнит-тестом без Postgres, как `pick_daily_id` и `compute_expiry`.

Язык — казахский, как и вся исходящая переписка бота (карточки чеков и обращений).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html import escape

from app.domain.analytics.percent import share
from app.domain.analytics.search import SearchSummary


@dataclass(frozen=True, slots=True)
class DailyReport:
    """Срез за сутки. `*_total` — накопленные величины, остальное — за отчётный день.

    Само по себе число просмотров ни о чём не говорит без контекста, в котором оно
    случилось: `catalog_size` — это контекст («фундамент истории
    аналитики»). Без него рост открытий за месяц роста каталога с 50 до 150 фильмов
    выглядел бы взрывом органики, хотя это просто больше SEO-страниц в индексе Google.
    Снимок пишется КАЖДЫЙ день в `daily_reports` (не пересчитывается на лету из
    `user_events` при каждом обращении) — иначе исторический размер каталога/аудитории
    потерялся бы: `movies`/`users` растут, и «каталог на 13.08» перезапросом уже не
    восстановить.
    """

    day: date
    users_total: int      # всего пользователей в БД (нажавшие /start тоже считаются)
    users_new: int        # из них появились сегодня
    subs_active: int      # активных подписок прямо сейчас
    catalog_size: int     # фильмов в каталоге на конец дня — знаменатель для нормировки
    opens_total: int      # открытий Mini App за день
    opens_unique: int     # ...из них уникальных людей (главная метрика живой аудитории)
    starts: int           # нажавших /start (в т.ч. пришедшие из SEO, до входа в Mini App)
    plays: int            # выданных видео за день (по подписке)
    free_plays: int       # ...и отдельно подарочных первых фильмов (СТАРАЯ механика)
    daily_plays: int      # ...и отдельно фильма дня (регулярный бесплатный крючок)
    paywalls: int         # упоров в пэйволл: хотел смотреть, но платить пока не стал
    subscribes: int       # активаций/продлений подписки за день
    expires: int          # истёкших подписок за день
    # Недельный бесплатный выбор — три РАЗНЫХ вопроса (см. `EventKind`):
    channel_gates: int = 0   # уткнулись в «жазылыңыз» — знаменатель всей затеи
    weekly_picks: int = 0    # взяли фильм на неделю (один на человека в неделю)
    weekly_plays: int = 0    # смотрели свой недельный, включая пересмотры
    # Движение в канале за сутки: сколько подписалось и сколько отписалось. Считается по
    # апдейтам `chat_member` (`channel_member_events`), а не выводится из числа
    # подписчиков: Telegram отдаёт только итог, а он скрывает ровно то, ради чего эти
    # цифры и нужны. «Пришли 40, ушли 35» и «не было движения» — это один и тот же «+5».
    channel_joins: int = 0
    channel_leaves: int = 0
    # Подписчиков у канала на конец дня. None — канал не настроен либо Telegram не
    # ответил; ноль и «не знаем» — разные вещи, и вторая обязана выглядеть в отчёте как
    # пропуск строки, а не как обвал аудитории до нуля.
    channel_members: int | None = None


def day_window(now: datetime) -> tuple[datetime, datetime]:
    """Скользящие «сутки»: от предыдущего запуска крона до этого (ровно 24 ч).

    Окно скользящее, а не «с местной полуночи»: отчёт уходит не в полночь, а вечером,
    и окно от полуночи обрубало бы хвост между временем отправки и полуночью — эти
    события не попали бы НИ В ОДИН отчёт (следующий день снова считает от своей
    полуночи). Особенно заметно в выходные, когда люди активны допоздна. Окно
    `[now-24ч, now)` дыр не
    оставляет: раз джоб идёт раз в сутки, оно ровно покрывает интервал между двумя
    соседними запусками — независимо от того, в котором часу отчёт настроен.
    """
    return now - timedelta(hours=24), now


def render_demand_block(summary: SearchSummary) -> str:
    """Блок «іздеп, таппағаны»: сколько искали, сколько зря и что именно не нашли.

    Один текст на дневной отчёт и недельный дайджест: вопрос там один и тот же — чего в
    каталоге нет, — а период понятен из шапки самого отчёта.

    Главная строка отчёта для наполнения каталога: люди прямым текстом называют, за чем
    пришли и ушли ни с чем. Показываем ТОП нулевых, а не весь поиск, — успешный поиск
    решений не меняет, а длинный список никто не дочитает.

    ⚠️ Запрос — текст ОТ ЧЕЛОВЕКА, и отчёт уходит как HTML: экранируем здесь. Без этого
    поиск по «<Шрек>» ломает разметку и отчёт не доставляется вообще.
    """
    if summary.searches == 0:
        return "🔎 Іздеу: сұрау болмады"
    lines = [f"🔎 Іздеу: {summary.searches} сұрау, {summary.missing} нәтижесіз"]
    if summary.top:
        lines.append("<b>Іздеп, таппағаны</b> (дауыстау кезегі):")
        lines += [
            f"{i}. {escape(demand.query)} — {demand.hits}× / {demand.people} адам"
            for i, demand in enumerate(summary.top, start=1)
        ]
    return "\n".join(lines)


def _channel_move(report: DailyReport, previous: DailyReport | None) -> str:
    """Движение канала за сутки: «(+12 / −3)» — пришли и ушли по головам.

    Плюс и минус порознь, а не один итог: день, в который пришли 40 и ушли 35, и день без
    единого движения дают одинаковый «+5», хотя это разные дни. Отток виден только так.

    Запасной вариант — разность вчерашнего и сегодняшнего снимков: движение мы считаем с
    того дня, как бот начал слушать `chat_member`, и за более ранние сутки (а также если
    апдейты почему-то не дошли) честнее показать итог, чем нарисовать «+0 / −0» там, где
    людей просто не считали.
    """
    if report.channel_joins or report.channel_leaves:
        return f" (+{report.channel_joins} / −{report.channel_leaves})"
    if previous is None or previous.channel_members is None or report.channel_members is None:
        return ""
    return f" ({report.channel_members - previous.channel_members:+d} тәулікте)"


def render_channel_block(report: DailyReport, previous: DailyReport | None) -> str:
    """Блок про канал и недельный выбор — та самая воронка, ради которой всё затевалось.

    Прирост канала сам по себе не говорит ничего: он мог случиться и без нас. Поэтому
    рядом стоят `channel_gates → weekly_picks` — сколько людей мы сами привели к
    требованию подписки и сколько из них дошло до фильма. Абсолютное число подписчиков —
    контекст, атрибуция — эти две цифры.

    Дельта считается ЗДЕСЬ, из вчерашнего снимка, а не хранится: это производная
    величина, как и проценты (см. докстринг `render_report`).
    """
    lines: list[str] = []
    if report.channel_members is not None:
        lines.append(f"📣 Арна: {report.channel_members}{_channel_move(report, previous)}")
    gate_rate = share(report.weekly_picks, report.channel_gates)
    lines.append(
        f"🎟 Апталық таңдау: {report.weekly_picks} алды, {report.weekly_plays} көрді"
    )
    if report.channel_gates:
        lines.append(
            f"   жазылуды сұрадық {report.channel_gates} → алды {report.weekly_picks}"
            f"{f' ({gate_rate}%)' if gate_rate is not None else ''}"
        )
    return "\n".join(lines)


def render_report(report: DailyReport, demand: SearchSummary | None = None,
                  previous: DailyReport | None = None) -> str:
    """Текст отчёта для личек админов (HTML-безопасен: цифры, наши подписи и
    экранированные поисковые запросы).

    Проценты считаются тут же, не в `AnalyticsService` и не хранятся в БД: это
    производные величины (снимок несёт только числители/знаменатели), а формула
    может меняться — тексту отчёта незачем тянуть за собой миграцию.
    """
    open_rate = share(report.opens_unique, report.starts)
    convert_rate = share(report.subscribes, report.paywalls)
    body = (
        f"📊 <b>Күнделікті есеп</b> · {report.day:%d.%m.%Y}\n"
        "———\n"
        f"👥 Барлық қолданушы: {report.users_total} (бүгін +{report.users_new})\n"
        f"✅ Белсенді жазылым: {report.subs_active}\n"
        f"🎬 Каталог: {report.catalog_size} фильм\n"
        "———\n"
        f"🤖 /start басты: {report.starts}\n"
        f"📱 Кинотеатрды ашты: {report.opens_unique} адам ({report.opens_total} рет)"
        f"{f' — {open_rate}%' if open_rate is not None else ''}\n"
        f"▶️ Жіберілген видео (жазылым): {report.plays}\n"
        # Воронка «сначала ценность, потом оплата». `Сыйлық фильм` — НАСЛЕДСТВО
        # одноразовой механики: новым он не выдаётся, и эта строка должна стремиться
        # к нулю. Живой бесплатный крючок теперь ниже, в блоке про канал.
        f"🎁 Сыйлық фильм (ескі): {report.free_plays}\n"
        f"📅 Күн фильмі: {report.daily_plays}\n"
        f"🔒 Пэйволл көрді: {report.paywalls}\n"
        f"💳 Жазылым қосылды: {report.subscribes}"
        f"{f' — конверсия {convert_rate}%' if convert_rate is not None else ''}\n"
        f"⌛️ Мерзімі бітті: {report.expires}\n"
        "———\n"
        f"{render_channel_block(report, previous)}"
    )
    # Спрос — отдельный блок и необязательный аргумент: он не из снимка, а из живого
    # запроса по журналу поисков, и отчёт обязан собираться и без него.
    if demand is None:
        return body
    return f"{body}\n———\n{render_demand_block(demand)}"
