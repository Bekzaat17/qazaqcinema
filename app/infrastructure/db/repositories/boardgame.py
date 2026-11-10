from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from typing import cast

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.boardgame import RoomRecord
from app.application.ports.quest import QuestStorageError
from app.domain.boardgame.game import Room
from app.infrastructure.db.quest_models import (
    BoardAwardModel,
    BoardRoomModel,
    QuestPlayerModel,
    QuestWeeklyScoreModel,
)

_CODEC = TypeAdapter(Room)


def _record(model: BoardRoomModel) -> RoomRecord:
    return RoomRecord(
        model.code, _CODEC.validate_python(model.state), dict(model.members), model.deadline
    )


def _dump(room: Room) -> dict[str, object]:
    # Типизация JSONB ограничена схемой Room, Any остаётся внутри адаптера pydantic.
    return cast(dict[str, object], _CODEC.dump_python(room, mode="json"))


class PgRoomRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, record: RoomRecord) -> None:
        try:
            self._session.add(
                BoardRoomModel(code=record.code, state=_dump(record.room), members=record.members)
            )
            await self._session.commit()
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise QuestStorageError("board_database_unavailable") from exc

    async def get(self, code: str) -> RoomRecord | None:
        try:
            model = await self._session.get(BoardRoomModel, code, populate_existing=True)
            record = _record(model) if model else None
            # Долгое ожидание обновлений не удерживает соединение с Postgres.
            await self._session.commit()
            return record
        except SQLAlchemyError as exc:
            raise QuestStorageError("board_database_unavailable") from exc

    @asynccontextmanager
    async def locked(self, code: str) -> AsyncIterator[RoomRecord | None]:
        try:
            model = await self._session.scalar(
                select(BoardRoomModel)
                .where(BoardRoomModel.code == code)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            yield _record(model) if model else None
            await self._session.commit()
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise QuestStorageError("board_database_unavailable") from exc
        except BaseException:
            await self._session.rollback()
            raise

    async def save(
        self, record: RoomRecord, winner_user_id: int | None, reward: int, week: date
    ) -> None:
        model = (
            await self._session.scalars(
                select(BoardRoomModel).where(BoardRoomModel.code == record.code)
            )
        ).one()
        model.state = _dump(record.room)
        model.members = dict(record.members)
        model.deadline = record.deadline
        model.updated_at = datetime.now(UTC)
        if winner_user_id is not None and reward:
            awarded = await self._session.scalar(
                pg_insert(BoardAwardModel)
                .values(user_id=winner_user_id, scenario_id=record.room.scenario_id)
                .on_conflict_do_nothing()
                .returning(BoardAwardModel.user_id)
            )
            if awarded is not None:
                player = pg_insert(QuestPlayerModel).values(user_id=winner_user_id, total_xp=reward)
                await self._session.execute(
                    player.on_conflict_do_update(
                        index_elements=["user_id"],
                        set_={"total_xp": QuestPlayerModel.total_xp + reward},
                    )
                )
                weekly = pg_insert(QuestWeeklyScoreModel).values(
                    user_id=winner_user_id, week=week, points=reward
                )
                await self._session.execute(
                    weekly.on_conflict_do_update(
                        index_elements=["user_id", "week"],
                        set_={"points": QuestWeeklyScoreModel.points + reward},
                    )
                )
