from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from typing import cast

from pydantic import TypeAdapter
from sqlalchemy import Integer, func, or_, select, update
from sqlalchemy import cast as sql_cast
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.boardgame import (
    CompletedGame,
    GameHistory,
    GameRank,
    GameRanking,
    PlayerAppearance,
    RoomRecord,
)
from app.application.ports.quest import QuestStorageError
from app.domain.boardgame.game import Room
from app.infrastructure.db.models import UserModel
from app.infrastructure.db.quest_models import (
    BoardAwardModel,
    BoardResultModel,
    BoardRoomModel,
    QuestPlayerModel,
    QuestWeeklyScoreModel,
)

_CODEC = TypeAdapter(Room)
_APPEARANCES = TypeAdapter(dict[str, PlayerAppearance])


def _record(model: BoardRoomModel) -> RoomRecord:
    return RoomRecord(
        model.code,
        _CODEC.validate_python(model.state),
        dict(model.members),
        model.deadline,
        _APPEARANCES.validate_python(model.state.get("_appearances", {})),
        model.state.get("_public") is True,
    )


def _dump(record: RoomRecord) -> dict[str, object]:
    # Типизация JSONB ограничена схемой Room, Any остаётся внутри адаптера pydantic.
    state = cast(dict[str, object], _CODEC.dump_python(record.room, mode="json"))
    state["_appearances"] = _APPEARANCES.dump_python(record.appearances, mode="json")
    state["_public"] = record.is_public
    return state


class PgRoomRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @asynccontextmanager
    async def lock_players(self, user_ids: tuple[int, ...]) -> AsyncIterator[None]:
        await self._session.execute(
            select(UserModel.telegram_id)
            .where(
                UserModel.telegram_id.in_(user_ids),
            )
            .order_by(UserModel.telegram_id)
            .with_for_update()
        )
        yield

    async def games_started(self, user_id: int) -> int:
        return int(
            await self._session.scalar(
                select(func.count())
                .select_from(BoardRoomModel)
                .where(
                    BoardRoomModel.members[str(user_id)].as_string().is_not(None),
                    BoardRoomModel.state["match"].as_string().is_not(None),
                )
            )
            or 0
        )

    async def touch_lobby(self, code: str, now: datetime) -> None:
        try:
            await self._session.execute(
                update(BoardRoomModel)
                .where(
                    BoardRoomModel.code == code,
                    BoardRoomModel.updated_at < now - timedelta(seconds=30),
                )
                .values(updated_at=now)
            )
            await self._session.commit()
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise QuestStorageError("board_database_unavailable") from exc

    async def public_rooms(self, now: datetime) -> list[RoomRecord]:
        try:
            models = await self._session.scalars(
                select(BoardRoomModel)
                .where(
                    BoardRoomModel.state["_public"].as_boolean().is_(True),
                    BoardRoomModel.state["closed"].as_boolean().is_(False),
                    BoardRoomModel.state["match"].as_string().is_(None),
                    func.jsonb_array_length(BoardRoomModel.state["seats"]) < 4,
                    BoardRoomModel.updated_at >= now - timedelta(minutes=2),
                )
                .order_by(BoardRoomModel.updated_at.desc(), BoardRoomModel.code)
                .limit(30)
            )
            result = [_record(model) for model in models]
            await self._session.commit()
            return result
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise QuestStorageError("board_database_unavailable") from exc

    async def my_rooms(self, user_id: int) -> list[RoomRecord]:
        try:
            models = await self._session.scalars(
                select(BoardRoomModel)
                .where(
                    BoardRoomModel.members[str(user_id)].as_string().is_not(None),
                    BoardRoomModel.state["closed"].as_boolean().is_(False),
                    or_(
                        BoardRoomModel.state["match"].as_string().is_(None),
                        BoardRoomModel.state["match"]["phase"].as_string() != "finished",
                    ),
                )
                .order_by(BoardRoomModel.updated_at.desc(), BoardRoomModel.code)
                .limit(30)
            )
            result = [_record(model) for model in models]
            await self._session.commit()
            return result
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise QuestStorageError("board_database_unavailable") from exc

    async def complete(self, game: CompletedGame) -> None:
        if not game.players:
            return
        await self._session.execute(
            pg_insert(BoardResultModel)
            .values(
                [
                    {
                        "code": game.code,
                        "user_id": p.user_id,
                        "name": p.name,
                        "scenario_id": game.scenario_id,
                        "board_id": game.board_id,
                        "rounds": game.rounds,
                        "finished_at": game.finished_at,
                        "winner_name": game.winner_name,
                        "player_count": game.player_count,
                        "capital": p.capital,
                        "won": p.won,
                    }
                    for p in game.players
                ]
            )
            .on_conflict_do_nothing()
        )

    async def history(self, user_id: int, offset: int) -> list[GameHistory]:
        try:
            models = await self._session.scalars(
                select(BoardResultModel)
                .where(
                    BoardResultModel.user_id == user_id,
                )
                .order_by(BoardResultModel.finished_at.desc(), BoardResultModel.code)
                .offset(offset)
                .limit(20)
            )
            result = [
                GameHistory(
                    m.code,
                    m.scenario_id,
                    m.board_id,
                    m.rounds,
                    m.finished_at,
                    m.winner_name,
                    m.player_count,
                    m.capital,
                    m.won,
                )
                for m in models
            ]
            await self._session.commit()
            return result
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise QuestStorageError("board_database_unavailable") from exc

    async def ranking(self, user_id: int) -> GameRanking:
        try:
            scores = (
                select(
                    BoardResultModel.user_id.label("user_id"),
                    func.count().label("played"),
                    func.sum(sql_cast(BoardResultModel.won, Integer)).label("wins"),
                )
                .group_by(BoardResultModel.user_id)
                .subquery()
            )
            ranked = select(
                scores,
                func.row_number()
                .over(
                    order_by=(
                        scores.c.wins.desc(),
                        (scores.c.wins * 1.0 / scores.c.played).desc(),
                        scores.c.user_id,
                    )
                )
                .label("rank"),
            ).subquery()
            latest_name = (
                select(BoardResultModel.name)
                .where(
                    BoardResultModel.user_id == ranked.c.user_id,
                )
                .order_by(BoardResultModel.finished_at.desc(), BoardResultModel.code)
                .limit(1)
                .scalar_subquery()
            )
            rows = await self._session.execute(
                select(ranked, latest_name.label("name"))
                .where(
                    or_(ranked.c.rank <= 50, ranked.c.user_id == user_id),
                )
                .order_by(ranked.c.rank)
            )
            entries = tuple(
                GameRank(int(r.rank), r.name, int(r.played), int(r.wins), r.user_id == user_id)
                for r in rows
            )
            result = GameRanking(
                tuple(e for e in entries if e.rank <= 50),
                next((e for e in entries if e.is_me), None),
            )
            await self._session.commit()
            return result
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise QuestStorageError("board_database_unavailable") from exc

    async def create(self, record: RoomRecord) -> None:
        try:
            self._session.add(
                BoardRoomModel(code=record.code, state=_dump(record), members=record.members)
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
        model.state = _dump(record)
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
