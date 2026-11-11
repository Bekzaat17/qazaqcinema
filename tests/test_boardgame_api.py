from __future__ import annotations

from pathlib import Path

import httpx
from app.api.app import create_app
from app.api.deps.auth import get_current_user
from app.application.ports.boardgame import GameRandom, RoomEvents, RoomRepository
from app.application.ports.rate_limit import RateLimiter
from app.application.ports.session import SessionStore
from app.application.services.boardgame_service import BoardGameService
from app.domain.boardgame.game import Catalog
from app.domain.entities.user import User
from app.infrastructure.content.boardgame import load_board_catalog
from app.infrastructure.db.repositories.boardgame import PgRoomRepository
from app.infrastructure.db.repositories.users import PgUserRepository
from dishka import Provider, Scope, make_async_container, provide
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_boardgame_repositories import Events, FixedRandom
from tests.test_quest_api import _Limiter, _Sessions

CATALOG = load_board_catalog(Path("web/public/boardgame/catalog-v2.json"))


async def test_people_join_ready_and_play_while_api_rejects_forged_money_and_dice(
    session: AsyncSession,
) -> None:
    class TestProvider(Provider):
        scope = Scope.APP

        @provide
        def repository(self) -> RoomRepository:
            return PgRoomRepository(session)

        @provide
        def definitions(self) -> Catalog:
            return CATALOG

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
    users = {}
    for uid in (42, 43, 99):
        users[uid] = await PgUserRepository(session).upsert(User(telegram_id=uid))

    async def current_user(request: Request) -> User:
        return users[int(request.headers.get("x-user", "42"))]

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        catalog = await client.get("/api/boardgame/catalog")
        assert catalog.status_code == 200 and len(catalog.json()["boards"]) == 2
        assert (
            await client.post(
                "/api/boardgame/rooms", json={"name": "Аян", "scenario_id": "almaty_first"}
            )
        ).status_code == 422
        assert (
            await client.get("/api/boardgame/rooms/ABCDEF1234", headers={"Authorization": "forged"})
        ).status_code == 401
        app.dependency_overrides[get_current_user] = current_user
        created = await client.post(
            "/api/boardgame/rooms", json={"name": "Аян", "scenario_id": "almaty_first"}
        )
        assert created.status_code == 200
        view = created.json()
        code = view["code"]
        me = view["me"]
        assert len(code) == 10 and "members" not in view and view["room"]["host"] == me
        assert created.headers["cache-control"] == "private, no-store"
        outsider = await client.get(f"/api/boardgame/rooms/{code}", headers={"x-user": "99"})
        assert outsider.status_code == 404
        joined = await client.post(
            f"/api/boardgame/rooms/{code.lower()}/join",
            headers={"x-user": "43"},
            json={"name": "Болат"},
        )
        assert joined.status_code == 200 and joined.json()["me"] != me

        async def command(
            kind: str, revision: int, uid: int = 42, **extra: object
        ) -> httpx.Response:
            return await client.post(
                f"/api/boardgame/rooms/{code}/command",
                headers={"x-user": str(uid)},
                json={"kind": kind, "revision": revision, **extra},
            )

        for extra in [{"dice": [6, 6]}, {"cash": 99999}, {"user_id": 43}, {"reward": 100000}]:
            assert (await command("roll", 1, **extra)).status_code == 422
        assert (await command("roll", True)).status_code == 422
        assert (await command("add_bot", 1, 43, target="balanced")).json()["outcome"] == "forbidden"
        assert (await command("start", 1)).json()["outcome"] == "not_ready"
        ready = await command("ready", 1, 43)
        assert ready.json()["outcome"] == "applied"
        started = await command("start", 2)
        assert started.json()["room"]["match"]["turn"] == 0
        assert (await command("roll", 3, 43)).json()["outcome"] == "forbidden"
        rolled = await command("roll", 3)
        assert rolled.json()["room"]["match"]["dice"] == [1, 1]
        bought = await command("buy", 4)
        assert bought.json()["room"]["match"]["players"][0]["cash"] == 1100
        assert (await command("buy", 4)).json()["outcome"] == "stale"
        ended = await command("end", 5)
        assert ended.json()["room"]["match"]["turn"] == 1
        other = await client.get(f"/api/boardgame/rooms/{code}", headers={"x-user": "43"})
        assert other.json()["room"] == ended.json()["room"]
        assert (await command("timeout", 6)).json()["outcome"] == "too_early"
    await container.close()
