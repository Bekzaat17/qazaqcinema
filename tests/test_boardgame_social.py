from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
from app.api.app import create_app
from app.api.deps.auth import get_current_user
from app.application.ports.boardgame import (
    CompletedGame,
    GameHistory,
    GameRandom,
    GameRank,
    GameRanking,
    RoomEvents,
    RoomRecord,
    RoomRepository,
)
from app.application.ports.rate_limit import RateLimiter
from app.application.ports.session import SessionStore
from app.application.services.boardgame_service import BoardGameService
from app.domain.boardgame.game import Action, Catalog, Command, Debt, Phase
from app.domain.entities.user import User
from app.infrastructure.content.boardgame import load_board_catalog
from app.infrastructure.db.quest_models import BoardRoomModel
from app.infrastructure.db.repositories.boardgame import _dump, _record
from dishka import Provider, Scope, make_async_container, provide
from fastapi import Request

from tests.test_boardgame_repositories import Events, FixedRandom
from tests.test_quest_api import _Limiter, _Sessions

_NOW = datetime(2026, 11, 11, tzinfo=UTC)
_CATALOG = load_board_catalog(Path("web/public/boardgame/catalog.json"))


class MemoryRooms:
    def __init__(self) -> None:
        self.records: dict[str, RoomRecord] = {}
        self.games: dict[str, CompletedGame] = {}
        self.touched: list[str] = []

    async def create(self, record: RoomRecord) -> None:
        self.records[record.code] = record

    @asynccontextmanager
    async def lock_players(self, user_ids: tuple[int, ...]) -> AsyncIterator[None]:
        yield

    async def games_started(self, user_id: int) -> int:
        return sum(
            str(user_id) in r.members and r.room.match is not None for r in self.records.values()
        )

    async def get(self, code: str) -> RoomRecord | None:
        return self.records.get(code)

    @asynccontextmanager
    async def locked(self, code: str) -> AsyncIterator[RoomRecord | None]:
        yield self.records.get(code)

    async def save(
        self, record: RoomRecord, winner_user_id: int | None, reward: int, week: date
    ) -> None:
        self.records[record.code] = record

    async def public_rooms(self, now: datetime) -> list[RoomRecord]:
        return list(self.records.values())

    async def my_rooms(self, user_id: int) -> list[RoomRecord]:
        return [
            r
            for r in self.records.values()
            if str(user_id) in r.members
            and not r.room.closed
            and (r.room.match is None or r.room.match.phase != Phase.FINISHED)
        ]

    async def touch_lobby(self, code: str, now: datetime) -> None:
        self.touched.append(code)

    async def complete(self, game: CompletedGame) -> None:
        self.games.setdefault(game.code, game)

    async def history(self, user_id: int, offset: int) -> list[GameHistory]:
        return [
            GameHistory(
                g.code,
                g.scenario_id,
                g.board_id,
                g.rounds,
                g.finished_at,
                g.winner_name,
                g.player_count,
                p.capital,
                p.won,
            )
            for g in self.games.values()
            for p in g.players
            if p.user_id == user_id
        ][offset : offset + 20]

    async def ranking(self, user_id: int) -> GameRanking:
        entries = tuple(
            GameRank(i + 1, p.name, 1, int(p.won), p.user_id == user_id)
            for g in self.games.values()
            for i, p in enumerate(g.players)
        )
        return GameRanking(entries, next((e for e in entries if e.is_me), None))


async def test_visibility_is_host_only_and_discovery_excludes_closed_full_and_started() -> None:
    repo = MemoryRooms()
    game = BoardGameService(repo, _CATALOG, FixedRandom(), Events())
    private = await game.create(42, "Owner", _CATALOG.scenarios[0].id)
    assert private and not await game.public_rooms(_NOW)
    assert (await game.set_public(99, private.code, True, _NOW)).record is None
    public = await game.set_public(42, private.code, True, _NOW)
    assert public.record and public.record.is_public
    assert [r.code for r in await game.public_rooms(_NOW)] == [private.code]
    model = BoardRoomModel(
        code=private.code, state=_dump(public.record), members=public.record.members
    )
    assert _record(model).is_public
    model.state = {k: v for k, v in model.state.items() if k != "_public"}
    assert not _record(model).is_public
    await game.view(42, private.code)
    assert repo.touched == [private.code]
    assert await game.view(99, private.code) is None
    joined = await game.join(43, "Guest", private.code, _NOW)
    assert joined.record
    assert (await game.set_public(43, private.code, False, _NOW)).record is None
    ready = await game.command(
        43, private.code, Command(joined.record.room.revision, Action.READY), _NOW
    )
    assert ready.record
    started = await game.command(
        42, private.code, Command(ready.record.room.revision, Action.START), _NOW
    )
    assert started.record and not await game.public_rooms(_NOW)
    assert (await game.set_public(42, private.code, False, _NOW)).outcome == "invalid"
    assert (await game.join(99, "Late", private.code, _NOW)).record is None
    repo.records[private.code] = replace(
        public.record, room=replace(public.record.room, closed=True)
    )
    assert not await game.public_rooms(_NOW)
    repo.records[private.code] = public.record
    for profile in ("balanced", "builder", "careful"):
        current = repo.records[private.code]
        await game.command(
            42, private.code, Command(current.room.revision, Action.ADD_BOT, profile), _NOW
        )
    assert not await game.public_rooms(_NOW)
    assert (await game.join(99, "Late", private.code, _NOW)).outcome == "full"


async def test_api_discovery_private_history_and_server_only_results() -> None:
    repo = MemoryRooms()

    class TestProvider(Provider):
        scope = Scope.APP

        @provide
        def repository(self) -> RoomRepository:
            return repo

        @provide
        def definitions(self) -> Catalog:
            return _CATALOG

        @provide
        def random(self) -> GameRandom:
            return FixedRandom()

        @provide
        def events(self) -> RoomEvents:
            return Events()

        @provide
        def limiter(self) -> RateLimiter:
            return _Limiter()

        @provide
        def sessions(self) -> SessionStore:
            return _Sessions()

        @provide
        def game(
            self,
            repository: RoomRepository,
            definitions: Catalog,
            random: GameRandom,
            events: RoomEvents,
        ) -> BoardGameService:
            return BoardGameService(repository, definitions, random, events)

    container = make_async_container(TestProvider())
    app = create_app(container)

    async def current_user(request: Request) -> User:
        return User(telegram_id=int(request.headers.get("x-user", "42")))

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (
            await client.get("/api/boardgame/rooms", headers={"Authorization": "forged"})
        ).status_code == 401
        app.dependency_overrides[get_current_user] = current_user
        response = await client.post(
            "/api/boardgame/rooms",
            json={"name": "Owner", "scenario_id": _CATALOG.scenarios[0].id, "is_public": True},
        )
        assert response.status_code == 200
        data = response.json()
        code = data["code"]
        listed = await client.get("/api/boardgame/rooms")
        assert listed.status_code == 200
        assert listed.json() == [
            {
                "code": code,
                "host_name": "Owner",
                "scenario_id": data["room"]["scenario_id"],
                "players": 1,
            }
        ]
        assert listed.headers["cache-control"] == "private, no-store"
        assert (await client.get("/api/boardgame/rooms/mine")).json()[0]["code"] == code
        assert (
            await client.get("/api/boardgame/rooms/mine", headers={"x-user": "99"})
        ).json() == []
        assert (
            await client.post(
                f"/api/boardgame/rooms/{code}/visibility",
                headers={"x-user": "99"},
                json={"is_public": False},
            )
        ).status_code == 404
        assert (await client.post("/api/boardgame/history", json={"won": True})).status_code == 405
        await client.post(
            f"/api/boardgame/rooms/{code}/join", headers={"x-user": "43"}, json={"name": "Guest"}
        )
        service = await container.get(BoardGameService)
        record = repo.records[code]
        ready = await service.command(43, code, Command(record.room.revision, Action.READY), _NOW)
        assert ready.record
        start = await service.command(
            42, code, Command(ready.record.room.revision, Action.START), _NOW
        )
        assert start.record and start.record.room.match
        record = start.record
        match = replace(
            record.room.match,
            phase=Phase.DEBT,
            debt=Debt(50),
            players=(replace(record.room.match.players[0], cash=0), record.room.match.players[1]),
        )
        repo.records[code] = replace(record, room=replace(record.room, match=match))
        command = {"revision": record.room.revision, "kind": "bankrupt"}
        finished = await client.post(f"/api/boardgame/rooms/{code}/command", json=command)
        assert finished.json()["room"]["match"]["phase"] == "finished"
        assert len(repo.games) == 1 and len(repo.games[code].players) == 2
        assert (await client.post(f"/api/boardgame/rooms/{code}/command", json=command)).json()[
            "outcome"
        ] == "stale"
        assert len(repo.games) == 1
        assert (await client.get("/api/boardgame/rooms/mine")).json() == []
        own = (await client.get("/api/boardgame/history")).json()
        winner = (await client.get("/api/boardgame/history", headers={"x-user": "43"})).json()
        assert len(own) == 1 and not own[0]["won"] and winner[0]["won"]
        assert (await client.get("/api/boardgame/history", headers={"x-user": "99"})).json() == []
        assert "user_id" not in own[0]
        assert (await client.get("/api/boardgame/history?offset=-1")).status_code == 422
        ranking = (await client.get("/api/boardgame/ranking", headers={"x-user": "43"})).json()
        assert ranking["me"]["wins"] == 1 and "user_id" not in ranking["me"]
    await container.close()


class Membership:
    def __init__(self) -> None:
        self.subscribed = False

    async def is_member(self, user_id: int) -> bool:
        return self.subscribed

    async def count_members(self) -> int | None:
        return None


async def test_first_three_starts_then_channel_gate_and_existing_games_continue() -> None:
    repo, membership = MemoryRooms(), Membership()
    service = BoardGameService(repo, _CATALOG, FixedRandom(), Events(), membership, "our_channel")
    for _ in range(3):
        record = await service.create(42, "Player", _CATALOG.scenarios[0].id)
        assert record
        added = await service.command(42, record.code, Command(0, Action.ADD_BOT, "balanced"), _NOW)
        assert added.record
        started = await service.command(
            42, record.code, Command(added.record.room.revision, Action.START), _NOW
        )
        assert started.record and started.record.room.match
    access = await service.access(42)
    assert access.games_started == 3 and access.free_left == 0 and not access.allowed
    assert access.channel_url == "https://t.me/our_channel"
    fourth = await service.create(42, "Player", _CATALOG.scenarios[0].id)
    assert fourth
    added = await service.command(42, fourth.code, Command(0, Action.ADD_BOT, "balanced"), _NOW)
    assert added.record
    command = Command(added.record.room.revision, Action.START)
    denied = await service.command(42, fourth.code, command, _NOW)
    assert (
        denied.outcome == "channel_required" and denied.record and denied.record.room.match is None
    )
    assert denied.blocked_seats == (fourth.room.host,)
    assert await repo.games_started(42) == 3
    # Подписка открывает четвёртую игру; повтор не расходует ещё одну попытку.
    membership.subscribed = True
    opened = await service.command(42, fourth.code, command, _NOW)
    assert opened.record and opened.record.room.match
    assert (await service.command(42, fourth.code, command, _NOW)).outcome == "stale"
    assert await repo.games_started(42) == 4
    membership.subscribed = False
    resumed = await service.command(
        42, fourth.code, Command(opened.record.room.revision, Action.ROLL), _NOW
    )
    assert resumed.outcome == "applied"
