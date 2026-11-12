from __future__ import annotations

from datetime import datetime

from sqlalchemy import distinct, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.quest import QuestStorageError
from app.domain.analytics.events import EventKind
from app.domain.analytics.game_report import GameReport, GameWinner
from app.domain.catalog.daily import TZ
from app.infrastructure.db.models import UserEventModel
from app.infrastructure.db.quest_models import BoardResultModel, QuestPlayerModel, QuestRunModel

_BOARD_EVENTS = (
    EventKind.BOARD_CREATE, EventKind.BOARD_JOIN, EventKind.BOARD_START, EventKind.BOARD_ACTION,
)


class PgGameAnalyticsRepository:
    def __init__(self, session: AsyncSession, admin_ids: tuple[int, ...]) -> None:
        self._session = session
        self._admins = admin_ids

    async def report(self, since: datetime, until: datetime) -> GameReport:
        try:
            events = (
                UserEventModel.created_at >= since, UserEventModel.created_at < until,
                UserEventModel.user_id.not_in(self._admins),
            )
            activity = (await self._session.execute(
                select(
                    func.count(distinct(UserEventModel.user_id)),
                    func.count(distinct(UserEventModel.meta)).filter(
                        UserEventModel.kind == EventKind.BOARD_CREATE.value
                    ),
                    func.count(distinct(UserEventModel.meta)).filter(
                        UserEventModel.kind == EventKind.BOARD_START.value
                    ),
                ).where(*events, UserEventModel.kind.in_([k.value for k in _BOARD_EVENTS]))
            )).one()
            completed_window = (
                BoardResultModel.finished_at >= since, BoardResultModel.finished_at < until,
                BoardResultModel.user_id.not_in(self._admins),
            )
            finished = (await self._session.execute(
                select(
                    func.count(distinct(BoardResultModel.code)),
                    func.count(distinct(BoardResultModel.user_id)),
                ).where(*completed_window)
            )).one()
            winners = await self._session.execute(
                select(func.max(BoardResultModel.name), func.count().label("wins"))
                .where(*completed_window, BoardResultModel.won.is_(True))
                .group_by(BoardResultModel.user_id)
                .order_by(func.count().desc(), BoardResultModel.user_id)
                .limit(5)
            )
            quests = (await self._session.execute(
                select(
                    func.count(distinct(QuestRunModel.user_id)), func.count(),
                    func.count().filter(
                        QuestRunModel.question_index >= func.cardinality(QuestRunModel.question_ids)
                    ),
                ).where(
                    QuestRunModel.day == until.astimezone(TZ).date(),
                    QuestRunModel.user_id.not_in(self._admins),
                )
            )).one()
            players_total = await self._session.scalar(
                select(func.count()).select_from(QuestPlayerModel)
                .where(QuestPlayerModel.user_id.not_in(self._admins))
            )
            result = GameReport(
                since=since, until=until,
                active_players=int(activity[0]), rooms_created=int(activity[1]),
                games_started=int(activity[2]), games_finished=int(finished[0]),
                finished_players=int(finished[1]), quest_players=int(quests[0]),
                quests_started=int(quests[1]), quests_finished=int(quests[2]),
                players_total=int(players_total or 0),
                winners=tuple(GameWinner(str(name), int(wins)) for name, wins in winners),
            )
            await self._session.commit()
            return result
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise QuestStorageError("game_analytics_unavailable") from exc
