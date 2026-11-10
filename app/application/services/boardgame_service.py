from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from uuid import uuid4

from app.application.ports.boardgame import GameRandom, RoomEvents, RoomRecord, RoomRepository
from app.domain.boardgame.game import (
    Action,
    Catalog,
    Command,
    Outcome,
    Phase,
    Room,
    Seat,
    apply_command,
    auto_turn,
)
from app.domain.subscription.weekly import week_start

COLORS = ("#4b9a88", "#d6a854", "#7899c4", "#b18cba")
TURN_SECONDS = 180


@dataclass(frozen=True, slots=True)
class RoomResult:
    record: RoomRecord | None
    outcome: Outcome


class BoardGameService:
    def __init__(
        self, repository: RoomRepository, catalog: Catalog, random: GameRandom, events: RoomEvents
    ) -> None:
        self._repository = repository
        self._catalog = catalog
        self._random = random
        self._events = events

    async def create(self, user_id: int, name: str, scenario_id: str) -> RoomRecord | None:
        if not any(s.id == scenario_id for s in self._catalog.scenarios):
            return None
        code = uuid4().hex[:10].upper()
        seat = Seat(uuid4().hex, name, COLORS[0], ready=True)
        record = RoomRecord(code, Room(0, seat.id, scenario_id, (seat,)), {str(user_id): seat.id})
        await self._repository.create(record)
        return record

    async def view(self, user_id: int, code: str, after: int | None = None) -> RoomRecord | None:
        record = await self._repository.get(code)
        if record is None or str(user_id) not in record.members:
            return None
        if after is not None and record.room.revision <= after and not record.room.closed:
            await self._events.wait(code, after, 25)
            record = await self._repository.get(code)
        return record if record and str(user_id) in record.members else None

    async def join(self, user_id: int, name: str, code: str, now: datetime) -> RoomResult:
        updated: RoomRecord | None = None
        async with self._repository.locked(code) as record:
            if record is None or record.room.closed:
                return RoomResult(None, Outcome.INVALID)
            if str(user_id) in record.members:
                return RoomResult(record, Outcome.APPLIED)
            if record.room.match is not None:
                return RoomResult(None, Outcome.INVALID)
            if len(record.room.seats) >= 4:
                return RoomResult(None, Outcome.FULL)
            used = {seat.color for seat in record.room.seats}
            color = next((color for color in COLORS if color not in used), COLORS[0])
            seat = Seat(uuid4().hex, name, color)
            room = replace(
                record.room, revision=record.room.revision + 1, seats=(*record.room.seats, seat)
            )
            updated = replace(record, room=room, members={**record.members, str(user_id): seat.id})
            await self._repository.save(updated, None, 0, week_start(now))
        await self._events.publish(code, updated.room.revision)
        return RoomResult(updated, Outcome.APPLIED)

    async def command(self, user_id: int, code: str, command: Command, now: datetime) -> RoomResult:
        async with self._repository.locked(code) as record:
            if record is None or str(user_id) not in record.members:
                return RoomResult(None, Outcome.FORBIDDEN)
            actor = record.members[str(user_id)]
            if command.kind == Action.TIMEOUT:
                if command.revision != record.room.revision:
                    return RoomResult(record, Outcome.STALE)
                if not record.deadline or now < record.deadline:
                    return RoomResult(record, Outcome.TOO_EARLY)
                room = auto_turn(self._catalog, record.room, self._random.below)
                outcome = Outcome.APPLIED
            else:
                result = apply_command(
                    self._catalog, record.room, actor, command, self._random.below
                )
                room, outcome = result.room, result.outcome
            if outcome != Outcome.APPLIED:
                return RoomResult(record, outcome)
            prior = record.room.match
            current = room.match
            deadline = record.deadline
            if current is not None and (
                prior is None or (prior.turn, prior.round) != (current.turn, current.round)
            ):
                deadline = now + timedelta(seconds=TURN_SECONDS)
            if current is not None and current.phase == Phase.FINISHED:
                deadline = None
            updated = replace(record, room=room, deadline=deadline)
            winner_user_id = None
            reward = 0
            if (
                current is not None
                and current.phase == Phase.FINISHED
                and (prior is None or prior.phase != Phase.FINISHED)
                and current.winner >= 0
            ):
                winner = current.players[current.winner]
                if not winner.bot:
                    winner_user_id = next(
                        (int(uid) for uid, pid in record.members.items() if pid == winner.id), None
                    )
                    reward = next(
                        s.reward for s in self._catalog.scenarios if s.id == room.scenario_id
                    )
            await self._repository.save(updated, winner_user_id, reward, week_start(now))
        await self._events.publish(code, updated.room.revision)
        return RoomResult(updated, outcome)

    async def leave(self, user_id: int, code: str, now: datetime) -> RoomResult:
        async with self._repository.locked(code) as record:
            if record is None or str(user_id) not in record.members:
                return RoomResult(None, Outcome.FORBIDDEN)
            if record.room.match is not None:
                # Начатая партия сохраняет состав: отсутствие игрока покрывает тайм-аут хода.
                return RoomResult(record, Outcome.INVALID)
            actor = record.members[str(user_id)]
            members = {uid: pid for uid, pid in record.members.items() if uid != str(user_id)}
            seats = tuple(seat for seat in record.room.seats if seat.id != actor)
            host = record.room.host
            if host == actor:
                host = next((seat.id for seat in seats if not seat.bot), "")
            room = replace(
                record.room,
                revision=record.room.revision + 1,
                host=host,
                seats=seats,
                closed=not members,
            )
            updated = replace(record, room=room, members=members)
            await self._repository.save(updated, None, 0, week_start(now))
        await self._events.publish(code, updated.room.revision)
        return RoomResult(updated, Outcome.APPLIED)
