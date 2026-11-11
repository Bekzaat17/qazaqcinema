from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.application.ports.boardgame import (
    ActiveRoom,
    CompletedGame,
    GameAccess,
    GameHistory,
    GameRandom,
    GameRanking,
    PlayerAppearance,
    PublicRoom,
    ResultPlayer,
    RoomEvents,
    RoomRecord,
    RoomRepository,
)
from app.application.ports.channel import ChannelMembership
from app.domain.boardgame.game import (
    Action,
    Catalog,
    Command,
    Outcome,
    Phase,
    Room,
    Seat,
    active_catalog,
    apply_command,
    auto_turn,
    board_for,
    net_worth,
)
from app.domain.subscription.weekly import week_start

COLORS = ("#4b9a88", "#d6a854", "#7899c4", "#b18cba")
TURN_SECONDS = 180


@dataclass(frozen=True, slots=True)
class RoomResult:
    record: RoomRecord | None
    outcome: Outcome
    blocked_seats: tuple[str, ...] = ()


class BoardGameService:
    def __init__(
        self,
        repository: RoomRepository,
        catalog: Catalog,
        random: GameRandom,
        events: RoomEvents,
        membership: ChannelMembership | None = None,
        channel_username: str = "",
    ) -> None:
        self._repository = repository
        self._catalog = catalog
        self._random = random
        self._events = events
        self._membership = membership
        self._channel_username = channel_username.lstrip("@")

    async def access(self, user_id: int) -> GameAccess:
        if self._membership is None or not self._channel_username:
            return GameAccess(0, 3, True, "")
        played = await self._repository.games_started(user_id)
        allowed = played < 3 or await self._membership.is_member(user_id)
        return GameAccess(
            played, max(0, 3 - played), allowed, f"https://t.me/{self._channel_username}"
        )

    async def create(
        self,
        user_id: int,
        name: str,
        scenario_id: str,
        appearance: PlayerAppearance | None = None,
        is_public: bool = False,
    ) -> RoomRecord | None:
        if not any(s.id == scenario_id for s in self._catalog.scenarios):
            return None
        code = uuid4().hex[:10].upper()
        seat = Seat(uuid4().hex, name, COLORS[0], ready=True)
        record = RoomRecord(
            code,
            Room(0, seat.id, scenario_id, (seat,)),
            {str(user_id): seat.id},
            appearances={seat.id: appearance or PlayerAppearance()},
            is_public=is_public,
        )
        await self._repository.create(record)
        return record

    async def public_rooms(self, now: datetime) -> list[PublicRoom]:
        records = await self._repository.public_rooms(now)
        return [
            PublicRoom(
                record.code,
                next(s.name for s in record.room.seats if s.id == record.room.host),
                record.room.scenario_id,
                len(record.room.seats),
            )
            for record in records
            if record.is_public
            and not record.room.closed
            and record.room.match is None
            and 0 < len(record.room.seats) < 4
        ]

    async def history(self, user_id: int, offset: int = 0) -> list[GameHistory]:
        return await self._repository.history(user_id, offset)

    async def my_rooms(self, user_id: int) -> list[ActiveRoom]:
        records = await self._repository.my_rooms(user_id)
        return [
            ActiveRoom(
                r.code,
                next(s.name for s in r.room.seats if s.id == r.room.host),
                r.room.scenario_id,
                len(r.room.seats),
                r.room.match is not None,
                r.is_public,
            )
            for r in records
        ]

    async def ranking(self, user_id: int) -> GameRanking:
        return await self._repository.ranking(user_id)

    async def set_public(
        self, user_id: int, code: str, is_public: bool, now: datetime
    ) -> RoomResult:
        async with self._repository.locked(code) as record:
            if record is None or record.members.get(str(user_id)) != record.room.host:
                return RoomResult(None, Outcome.FORBIDDEN)
            if record.room.match is not None or record.room.closed:
                return RoomResult(record, Outcome.INVALID)
            if record.is_public == is_public:
                return RoomResult(record, Outcome.APPLIED)
            updated = replace(
                record,
                is_public=is_public,
                room=replace(record.room, revision=record.room.revision + 1),
            )
            await self._repository.save(updated, None, 0, week_start(now))
        await self._events.publish(code, updated.room.revision)
        return RoomResult(updated, Outcome.APPLIED)

    async def view(self, user_id: int, code: str, after: int | None = None) -> RoomRecord | None:
        record = await self._repository.get(code)
        if record is None or str(user_id) not in record.members:
            return None
        if (
            record.is_public
            and record.room.match is None
            and record.members[str(user_id)] == record.room.host
        ):
            await self._repository.touch_lobby(code, datetime.now(UTC))
        if after is not None and record.room.revision <= after and not record.room.closed:
            await self._events.wait(code, after, 25)
            record = await self._repository.get(code)
        return record if record and str(user_id) in record.members else None

    async def join(
        self,
        user_id: int,
        name: str,
        code: str,
        now: datetime,
        appearance: PlayerAppearance | None = None,
    ) -> RoomResult:
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
            updated = replace(
                record,
                room=room,
                members={**record.members, str(user_id): seat.id},
                appearances={**record.appearances, seat.id: appearance or PlayerAppearance()},
            )
            await self._repository.save(updated, None, 0, week_start(now))
        await self._events.publish(code, updated.room.revision)
        return RoomResult(updated, Outcome.APPLIED)

    async def set_appearance(
        self,
        user_id: int,
        code: str,
        appearance: PlayerAppearance,
        now: datetime,
    ) -> RoomResult:
        async with self._repository.locked(code) as record:
            if record is None or str(user_id) not in record.members:
                return RoomResult(None, Outcome.FORBIDDEN)
            actor = record.members[str(user_id)]
            if record.appearances.get(actor) == appearance:
                return RoomResult(record, Outcome.APPLIED)
            updated = replace(
                record,
                room=replace(record.room, revision=record.room.revision + 1),
                appearances={**record.appearances, actor: appearance},
            )
            await self._repository.save(updated, None, 0, week_start(now))
        await self._events.publish(code, updated.room.revision)
        return RoomResult(updated, Outcome.APPLIED)

    async def command(self, user_id: int, code: str, command: Command, now: datetime) -> RoomResult:
        async with self._repository.locked(code) as record:
            if record is None or str(user_id) not in record.members:
                return RoomResult(None, Outcome.FORBIDDEN)
            actor = record.members[str(user_id)]
            if (
                command.kind == Action.START
                and record.room.match is None
                and actor == record.room.host
                and self._membership is not None
                and self._channel_username
            ):
                # Блокировки пользователей держатся до commit комнаты: два параллельных
                # старта не могут одновременно потратить последнюю бесплатную партию.
                async with self._repository.lock_players(
                    tuple(sorted(int(uid) for uid in record.members))
                ):
                    blocked_players = []
                    for uid, pid in record.members.items():
                        if not (await self.access(int(uid))).allowed:
                            blocked_players.append(pid)
                    blocked = tuple(blocked_players)
                    if blocked:
                        return RoomResult(record, Outcome.CHANNEL_REQUIRED, blocked)
            if command.kind == Action.TIMEOUT:
                if command.revision != record.room.revision:
                    return RoomResult(record, Outcome.STALE)
                match = record.room.match
                bot_turn = (
                    match is not None
                    and match.phase != Phase.FINISHED
                    and bool(match.players[match.turn].bot)
                )
                if not bot_turn and (not record.deadline or now < record.deadline):
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
                        s.reward
                        for s in active_catalog(self._catalog, room).scenarios
                        if s.id == room.scenario_id
                    )
            await self._repository.save(updated, winner_user_id, reward, week_start(now))
            if (
                current is not None
                and current.phase == Phase.FINISHED
                and (prior is None or prior.phase != Phase.FINISHED)
            ):
                board = board_for(self._catalog, room)
                members = {pid: int(uid) for uid, pid in record.members.items()}
                await self._repository.complete(
                    CompletedGame(
                        code,
                        room.scenario_id,
                        board.id,
                        current.round,
                        now,
                        current.players[current.winner].name if current.winner >= 0 else "",
                        len(current.players),
                        tuple(
                            ResultPlayer(
                                members[p.id],
                                p.name,
                                net_worth(board, current, i),
                                i == current.winner,
                            )
                            for i, p in enumerate(current.players)
                            if p.id in members
                        ),
                    )
                )
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
            updated = replace(
                record,
                room=room,
                members=members,
                appearances={
                    key: value for key, value in record.appearances.items() if key != actor
                },
            )
            await self._repository.save(updated, None, 0, week_start(now))
        await self._events.publish(code, updated.room.revision)
        return RoomResult(updated, Outcome.APPLIED)
