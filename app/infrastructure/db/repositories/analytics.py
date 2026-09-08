"""Pg-адаптеры аналитики: журнал событий, спрос словами, снимки отчётов, вехи роста.

Запись событий и поисковых запросов — **fail-open**: статистика не вправе ронять
основной сценарий, поэтому сбой БД тут гасится логом, а не исключением наружу.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy import ColumnElement, distinct, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.analytics.events import EventKind
from app.domain.analytics.milestone import Milestone
from app.domain.analytics.report import DailyReport
from app.domain.analytics.search import SearchDemand
from app.infrastructure.db.models import (
    DailyReportModel,
    MilestoneModel,
    SearchQueryModel,
    UserEventModel,
)

logger = logging.getLogger(__name__)


def _milestone_to_domain(model: MilestoneModel) -> Milestone:
    return Milestone(
        id=model.id,
        occurred_at=model.occurred_at,
        label=model.label,
        created_by=model.created_by,
    )


def _daily_report_to_domain(model: DailyReportModel) -> DailyReport:
    return DailyReport(
        day=model.day,
        users_total=model.users_total,
        users_new=model.users_new,
        subs_active=model.subs_active,
        catalog_size=model.catalog_size,
        opens_total=model.opens_total,
        opens_unique=model.opens_unique,
        starts=model.starts,
        plays=model.plays,
        free_plays=model.free_plays,
        daily_plays=model.daily_plays,
        paywalls=model.paywalls,
        subscribes=model.subscribes,
        expires=model.expires,
    )


def _event_window(
    kind: EventKind, since: datetime, until: datetime
) -> tuple[ColumnElement[bool], ...]:
    """Условие «событие вида kind в полуинтервале [since, until)» — под составной индекс."""
    return (
        UserEventModel.kind == kind.value,
        UserEventModel.created_at >= since,
        UserEventModel.created_at < until,
    )


def _search_window(since: datetime, until: datetime) -> tuple[ColumnElement[bool], ...]:
    """Полуинтервал `[since, until)` — как у окна событий: сутки не пересекаются."""
    return (
        SearchQueryModel.created_at >= since,
        SearchQueryModel.created_at < until,
    )


class PgUserEventRepository:
    """Журнал значимых действий. Запись — **fail-open** (деградация в адаптере, как у Redis)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user_id: int, kind: EventKind, meta: str | None = None) -> None:
        try:
            self._session.add(UserEventModel(user_id=user_id, kind=kind.value, meta=meta))
            await self._session.commit()
        except SQLAlchemyError:
            # Статистика не вправе ронять основной сценарий: выданное видео и активная
            # подписка важнее строчки в отчёте. rollback обязателен — после сбоя
            # транзакция Postgres «аварийная», и без него упал бы следующий запрос
            # в этой же сессии, уже по делу.
            logger.warning("Событие %s юзера %s не записано", kind, user_id, exc_info=True)
            await self._session.rollback()

    async def count(self, kind: EventKind, since: datetime, until: datetime) -> int:
        stmt = (
            select(func.count())
            .select_from(UserEventModel)
            .where(*_event_window(kind, since, until))
        )
        return int(await self._session.scalar(stmt) or 0)

    async def count_unique_users(self, kind: EventKind, since: datetime, until: datetime) -> int:
        stmt = select(func.count(distinct(UserEventModel.user_id))).where(
            *_event_window(kind, since, until)
        )
        return int(await self._session.scalar(stmt) or 0)


class PgSearchQueryRepository:
    """Спрос словами (`search_queries`). Запись — **fail-open**, как у журнала событий."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user_id: int, query: str, found: int) -> None:
        try:
            self._session.add(SearchQueryModel(user_id=user_id, query=query, found=found))
            await self._session.commit()
        except SQLAlchemyError:
            # Тот же принцип, что у `PgUserEventRepository.add`: сбой аналитики не вправе
            # уронить сам поиск — человек ищет кино, а не пополняет нам статистику.
            # rollback обязателен: без него аварийная транзакция уронила бы следующий
            # запрос в этой же сессии, уже по делу.
            logger.warning("Поисковый запрос юзера %s не записан", user_id, exc_info=True)
            await self._session.rollback()

    async def count(self, since: datetime, until: datetime) -> int:
        stmt = (
            select(func.count())
            .select_from(SearchQueryModel)
            .where(*_search_window(since, until))
        )
        return int(await self._session.scalar(stmt) or 0)

    async def count_missing(self, since: datetime, until: datetime) -> int:
        stmt = (
            select(func.count())
            .select_from(SearchQueryModel)
            .where(*_search_window(since, until), SearchQueryModel.found == 0)
        )
        return int(await self._session.scalar(stmt) or 0)

    async def top(self, since: datetime, until: datetime, limit: int) -> list[SearchDemand]:
        return await self._top(since, until, limit, missing_only=False)

    async def top_missing(
        self, since: datetime, until: datetime, limit: int
    ) -> list[SearchDemand]:
        return await self._top(since, until, limit, missing_only=True)

    async def _top(
        self, since: datetime, until: datetime, limit: int, *, missing_only: bool
    ) -> list[SearchDemand]:
        """Группировка по уже нормализованному `query` (см. `domain/analytics/search`).

        Оба публичных метода отличаются ровно одним предикатом, поэтому запрос один:
        разница «что ищут» и «чего не нашли» — в данных, не в логике.
        """
        hits = func.count().label("hits")
        people = func.count(distinct(SearchQueryModel.user_id)).label("people")
        conditions: list[ColumnElement[bool]] = list(_search_window(since, until))
        if missing_only:
            conditions.append(SearchQueryModel.found == 0)
        stmt = (
            select(SearchQueryModel.query, hits, people)
            .where(*conditions)
            .group_by(SearchQueryModel.query)
            # Второй ключ — число разных людей: пять человек с одним запросом весомее
            # пяти попыток одного, а по частоте они неотличимы. Третий — сам текст,
            # чтобы порядок был устойчив и отчёт не «дрожал» между прогонами.
            .order_by(hits.desc(), people.desc(), SearchQueryModel.query)
            .limit(limit)
        )
        rows = await self._session.execute(stmt)
        return [
            SearchDemand(query=row.query, hits=row.hits, people=row.people)
            for row in rows
        ]


class PgDailyReportRepository:
    """История снимков (`daily_reports`). Одна операция — upsert по `day`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, report: DailyReport) -> None:
        values = {
            "day": report.day,
            "users_total": report.users_total,
            "users_new": report.users_new,
            "subs_active": report.subs_active,
            "catalog_size": report.catalog_size,
            "opens_total": report.opens_total,
            "opens_unique": report.opens_unique,
            "starts": report.starts,
            "plays": report.plays,
            "free_plays": report.free_plays,
            "daily_plays": report.daily_plays,
            "paywalls": report.paywalls,
            "subscribes": report.subscribes,
            "expires": report.expires,
        }
        stmt = pg_insert(DailyReportModel).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["day"],
            set_={
                **{key: stmt.excluded[key] for key in values if key != "day"},
                # created_at «Core»-апдейт не проходит через ORM onupdate — двигаем явно,
                # чтобы по нему было видно, что снимок за этот день переписан повторно.
                "created_at": func.now(),
            },
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def list_range(self, start: date, end: date) -> list[DailyReport]:
        stmt = (
            select(DailyReportModel)
            .where(DailyReportModel.day >= start, DailyReportModel.day <= end)
            .order_by(DailyReportModel.day)
        )
        result = await self._session.scalars(stmt)
        return [_daily_report_to_domain(model) for model in result]


class PgMilestoneRepository:
    """Лента вех роста (`milestones`). Пишет и читает админ-команда `/milestone`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, label: str, occurred_at: datetime, created_by: int) -> Milestone:
        model = MilestoneModel(label=label, occurred_at=occurred_at, created_by=created_by)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _milestone_to_domain(model)

    async def list_recent(self, limit: int) -> list[Milestone]:
        stmt = select(MilestoneModel).order_by(MilestoneModel.occurred_at.desc()).limit(limit)
        result = await self._session.scalars(stmt)
        return [_milestone_to_domain(model) for model in result]

    async def list_between(self, since: datetime, until: datetime) -> list[Milestone]:
        stmt = (
            select(MilestoneModel)
            .where(MilestoneModel.occurred_at >= since, MilestoneModel.occurred_at < until)
            .order_by(MilestoneModel.occurred_at)
        )
        result = await self._session.scalars(stmt)
        return [_milestone_to_domain(model) for model in result]
