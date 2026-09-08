"""Сбор цифр для ежедневного отчёта и еженедельного дайджеста.

Считает БД (COUNT по индексам), наружу идут числа и один короткий список — топ
поисковых запросов без результата; строки пользователей и событий сюда не грузятся,
поэтому стоимость отчёта не растёт с базой. Как это выглядит
и какие сутки считать — домен (`domain/analytics/report`, `.../weekly_report`), когда
слать — планировщик.
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime, time, tzinfo

from app.application.ports.repositories import (
    DailyReportRepository,
    MilestoneRepository,
    MovieRepository,
    SearchQueryRepository,
    UserEventRepository,
    UserRepository,
)
from app.domain.analytics.events import EventKind
from app.domain.analytics.report import DailyReport, day_window
from app.domain.analytics.search import SearchSummary
from app.domain.analytics.weekly_report import (
    WeeklyReport,
    build_weekly_report,
    previous_week_range,
    week_range,
)


class AnalyticsService:
    def __init__(
        self,
        users: UserRepository,
        events: UserEventRepository,
        movies: MovieRepository,
        reports: DailyReportRepository,
        milestones: MilestoneRepository,
        searches: SearchQueryRepository,
        admin_ids: Collection[int] = (),
    ) -> None:
        self._users = users
        self._events = events
        self._movies = movies
        self._reports = reports
        self._milestones = milestones
        self._searches = searches
        # Админы — не аудитория: их заходы служебные. События до журнала вообще не
        # доходят (`AdminBlindEventRepository`), а вот в `users` они лежат наравне со
        # всеми — поэтому счётчики людей исключают их явно.
        self._admins = admin_ids

    async def daily_report(self, now: datetime, tz: tzinfo) -> DailyReport:
        """Срез за скользящие сутки до `now` (границы — домен); `tz` только для даты в шапке.

        Снимок сразу пишется в историю (`daily_reports`) — это тот же вызов, которым
        планировщик собирает текст для админов, отдельного джоба на запись нет.
        """
        since, until = day_window(now)
        report = DailyReport(
            day=now.astimezone(tz).date(),
            users_total=await self._users.count_all(self._admins),
            users_new=await self._users.count_created_since(since, self._admins),
            subs_active=await self._users.count_active(now, self._admins),
            catalog_size=await self._movies.count_all(),
            opens_total=await self._events.count(EventKind.OPEN, since, until),
            opens_unique=await self._events.count_unique_users(EventKind.OPEN, since, until),
            starts=await self._events.count(EventKind.START, since, until),
            plays=await self._events.count(EventKind.PLAY, since, until),
            free_plays=await self._events.count(EventKind.FREE_PLAY, since, until),
            daily_plays=await self._events.count(EventKind.DAILY_PLAY, since, until),
            paywalls=await self._events.count(EventKind.PAYWALL, since, until),
            subscribes=await self._events.count(EventKind.SUBSCRIBE, since, until),
            expires=await self._events.count(EventKind.EXPIRE, since, until),
        )
        await self._reports.save(report)
        return report

    async def search_demand(self, now: datetime, limit: int) -> SearchSummary:
        """Спрос за те же скользящие сутки, что и отчёт: сколько искали и чего не нашли.

        Отдельный вызов, а не поле снимка: список не хранится (см. `SearchSummary`), а
        сутки берутся тем же `day_window`, иначе цифры отчёта и спроса разъехались бы.
        """
        since, until = day_window(now)
        return await self._demand(since, until, limit)

    async def _demand(
        self, since: datetime, until: datetime, limit: int
    ) -> SearchSummary:
        """Сводка спроса за любое окно — три запроса по журналу поисков."""
        return SearchSummary(
            searches=await self._searches.count(since, until),
            missing=await self._searches.count_missing(since, until),
            top=tuple(await self._searches.top_missing(since, until, limit)),
        )

    async def weekly_report(
        self, now: datetime, tz: tzinfo, demand_top: int = 0
    ) -> WeeklyReport:
        """Дайджест за последние 7 суток из уже сохранённых снимков `daily_reports`.

        Запускать ПОСЛЕ `daily_report` того же дня: иначе сегодняшний снимок ещё не
        записан и «последние 7 суток» упрутся во вчера. Планировщик разводит их по
        времени (`scheduler.py`), а не порядком вызова здесь.
        """
        today = now.astimezone(tz).date()
        cur_start, cur_end = week_range(today)
        prev_start, prev_end = previous_week_range(today)
        current_days = await self._reports.list_range(cur_start, cur_end)
        previous_days = await self._reports.list_range(prev_start, prev_end)
        window_start = datetime.combine(cur_start, time.min, tzinfo=tz)
        milestones = await self._milestones.list_between(window_start, now)
        # Спрос — тем же окном, что вехи: иначе список «искали и не нашли» относился бы
        # к другому периоду, чем цифры дайджеста. `demand_top=0` → сводку не запрашиваем.
        demand = (
            await self._demand(window_start, now, demand_top) if demand_top else None
        )
        return build_weekly_report(today, current_days, previous_days, milestones, demand)
