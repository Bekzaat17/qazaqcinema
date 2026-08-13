"""Сбор цифр для ежедневного отчёта.

Считает БД (COUNT по индексам), наружу идут только числа — строки пользователей и
событий сюда не грузятся, поэтому стоимость отчёта не растёт с базой. Как это выглядит
и какие сутки считать — домен (`domain/analytics/report`), когда слать — планировщик.
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime, tzinfo

from app.application.ports.repositories import UserEventRepository, UserRepository
from app.domain.analytics.events import EventKind
from app.domain.analytics.report import DailyReport, day_window


class AnalyticsService:
    def __init__(
        self,
        users: UserRepository,
        events: UserEventRepository,
        admin_ids: Collection[int] = (),
    ) -> None:
        self._users = users
        self._events = events
        # Админы — не аудитория: их заходы служебные. События до журнала вообще не
        # доходят (`AdminBlindEventRepository`), а вот в `users` они лежат наравне со
        # всеми — поэтому счётчики людей исключают их явно.
        self._admins = admin_ids

    async def daily_report(self, now: datetime, tz: tzinfo) -> DailyReport:
        """Срез за «сегодня» в часовом поясе `tz` (в БД всё в UTC — границы считает домен)."""
        since, until = day_window(now, tz)
        return DailyReport(
            day=now.astimezone(tz).date(),
            users_total=await self._users.count_all(self._admins),
            users_new=await self._users.count_created_since(since, self._admins),
            subs_active=await self._users.count_active(now, self._admins),
            opens_total=await self._events.count(EventKind.OPEN, since, until),
            opens_unique=await self._events.count_unique_users(EventKind.OPEN, since, until),
            plays=await self._events.count(EventKind.PLAY, since, until),
            subscribes=await self._events.count(EventKind.SUBSCRIBE, since, until),
            expires=await self._events.count(EventKind.EXPIRE, since, until),
        )
