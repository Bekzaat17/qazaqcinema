from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date

from sqlalchemy import ColumnElement, and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.quest import QuestStorageError
from app.domain.quest.game import (
    QUESTIONS_PER_RUN,
    STONE_REWARD,
    WOOD_REWARD,
    Progress,
    RankEntry,
    RankingPeriod,
    Run,
)
from app.infrastructure.db.quest_models import (
    QuestChannelPostModel,
    QuestPlayerModel,
    QuestRunModel,
    QuestWeeklyScoreModel,
)


def _run(model: QuestRunModel) -> Run:
    return Run(
        model.id,
        model.user_id,
        model.quest_id,
        model.day,
        tuple(model.question_ids),
        model.question_index,
        tuple(model.tried),
        model.points,
    )


def _progress(model: QuestPlayerModel) -> Progress:
    return Progress(
        model.total_xp,
        tuple(model.completed_quests),
        (),
        model.wood,
        model.stone,
        tuple(model.buildings.items()),
    )


class PgQuestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @asynccontextmanager
    async def _transaction(self) -> AsyncIterator[None]:
        try:
            yield
            await self._session.commit()
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise QuestStorageError("quest_database_unavailable") from exc
        except BaseException:
            await self._session.rollback()
            raise

    async def progress(self, user_id: int, day: date) -> Progress:
        try:
            player = await self._session.get(QuestPlayerModel, user_id)
            if player is None:
                return Progress()
            today = await self._session.scalars(
                select(QuestRunModel.quest_id).where(
                    QuestRunModel.user_id == user_id,
                    QuestRunModel.day == day,
                    QuestRunModel.question_index == QUESTIONS_PER_RUN,
                )
            )
            return Progress(
                player.total_xp,
                tuple(player.completed_quests),
                tuple(today),
                player.wood,
                player.stone,
                tuple(player.buildings.items()),
            )
        except SQLAlchemyError as exc:
            raise QuestStorageError("quest_database_unavailable") from exc

    async def start(self, run: Run) -> Run:
        async with self._transaction():
            await self._session.execute(
                pg_insert(QuestPlayerModel).values(user_id=run.user_id).on_conflict_do_nothing()
            )
            await self._session.execute(
                pg_insert(QuestRunModel)
                .values(
                    id=run.id,
                    user_id=run.user_id,
                    quest_id=run.quest_id,
                    day=run.day,
                    question_ids=list(run.question_ids),
                )
                .on_conflict_do_nothing(constraint="uq_quest_run_daily")
            )
            model = (
                await self._session.scalars(
                    select(QuestRunModel).where(
                        QuestRunModel.user_id == run.user_id,
                        QuestRunModel.quest_id == run.quest_id,
                        QuestRunModel.day == run.day,
                    )
                )
            ).one()
            return _run(model)

    @asynccontextmanager
    async def locked_run(self, run_id: str, user_id: int) -> AsyncIterator[Run | None]:
        async with self._transaction():
            model = await self._session.scalar(
                select(QuestRunModel)
                .where(
                    QuestRunModel.id == run_id,
                    QuestRunModel.user_id == user_id,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            yield _run(model) if model else None

    async def save_answer(self, run: Run, week: date) -> None:
        # Вызывается только внутри locked_run; награда коммитится вместе с последним ответом.
        await self._session.execute(
            update(QuestRunModel)
            .where(QuestRunModel.id == run.id)
            .values(
                question_index=run.index,
                tried=list(run.tried),
                points=run.points,
            )
        )
        if run.complete:
            player = (
                await self._session.scalars(
                    select(QuestPlayerModel)
                    .where(
                        QuestPlayerModel.user_id == run.user_id,
                    )
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).one()
            player.total_xp += run.points
            player.wood += WOOD_REWARD
            player.stone += STONE_REWARD
            if run.quest_id not in player.completed_quests:
                player.completed_quests = [*player.completed_quests, run.quest_id]
            stmt = pg_insert(QuestWeeklyScoreModel).values(
                user_id=run.user_id,
                week=week,
                points=run.points,
            )
            await self._session.execute(
                stmt.on_conflict_do_update(
                    index_elements=["user_id", "week"],
                    set_={"points": QuestWeeklyScoreModel.points + run.points},
                )
            )

    @asynccontextmanager
    async def locked_village(self, user_id: int) -> AsyncIterator[Progress]:
        async with self._transaction():
            await self._session.execute(
                pg_insert(QuestPlayerModel).values(user_id=user_id).on_conflict_do_nothing()
            )
            player = (
                await self._session.scalars(
                    select(QuestPlayerModel)
                    .where(
                        QuestPlayerModel.user_id == user_id,
                    )
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).one()
            yield _progress(player)

    async def save_village(self, user_id: int, progress: Progress) -> None:
        await self._session.execute(
            update(QuestPlayerModel)
            .where(
                QuestPlayerModel.user_id == user_id,
            )
            .values(wood=progress.wood, stone=progress.stone, buildings=dict(progress.buildings))
        )

    async def leaders(
        self,
        period: RankingPeriod,
        week: date,
        limit: int,
    ) -> tuple[RankEntry, ...]:
        try:
            if period == RankingPeriod.WEEK:
                stmt = (
                    select(QuestWeeklyScoreModel.user_id, QuestWeeklyScoreModel.points)
                    .where(
                        QuestWeeklyScoreModel.week == week,
                        QuestWeeklyScoreModel.points > 0,
                    )
                    .order_by(QuestWeeklyScoreModel.points.desc(), QuestWeeklyScoreModel.user_id)
                )
            else:
                stmt = (
                    select(QuestPlayerModel.user_id, QuestPlayerModel.total_xp)
                    .where(
                        QuestPlayerModel.total_xp > 0,
                    )
                    .order_by(QuestPlayerModel.total_xp.desc(), QuestPlayerModel.user_id)
                )
            rows = (await self._session.execute(stmt.limit(limit))).all()
            return tuple(RankEntry(row[0], i + 1, row[1]) for i, row in enumerate(rows))
        except SQLAlchemyError as exc:
            raise QuestStorageError("quest_database_unavailable") from exc

    async def rank(
        self,
        user_id: int,
        period: RankingPeriod,
        week: date,
    ) -> RankEntry | None:
        try:
            filters: tuple[ColumnElement[bool], ...]
            if period == RankingPeriod.WEEK:
                points = QuestWeeklyScoreModel.points
                user = QuestWeeklyScoreModel.user_id
                filters = (QuestWeeklyScoreModel.week == week,)
            else:
                points = QuestPlayerModel.total_xp
                user = QuestPlayerModel.user_id
                filters = ()
            score = await self._session.scalar(select(points).where(user == user_id, *filters))
            if not score:
                return None
            ahead = await self._session.scalar(
                select(func.count()).where(
                    *filters,
                    or_(points > score, and_(points == score, user < user_id)),
                )
            )
            return RankEntry(user_id, int(ahead or 0) + 1, score)
        except SQLAlchemyError as exc:
            raise QuestStorageError("quest_database_unavailable") from exc


class PgQuestChannelStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def message_id(self, key: str) -> int | None:
        try:
            return await self._session.scalar(
                select(QuestChannelPostModel.message_id).where(
                    QuestChannelPostModel.key == key,
                )
            )
        except SQLAlchemyError as exc:
            raise QuestStorageError("quest_channel_store_unavailable") from exc

    async def reserve(self, key: str) -> bool:
        try:
            claimed = await self._session.scalar(
                pg_insert(QuestChannelPostModel)
                .values(key=key)
                .on_conflict_do_nothing()
                .returning(QuestChannelPostModel.key)
            )
            # Резервирование сохраняем ДО Telegram: неопределённая доставка не создаёт спам.
            await self._session.commit()
            return claimed is not None
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise QuestStorageError("quest_channel_store_unavailable") from exc

    async def delivered(self, key: str, message_id: int) -> None:
        try:
            await self._session.execute(
                update(QuestChannelPostModel)
                .where(
                    QuestChannelPostModel.key == key,
                )
                .values(message_id=message_id)
            )
            await self._session.commit()
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise QuestStorageError("quest_channel_store_unavailable") from exc
