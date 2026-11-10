from __future__ import annotations

import httpx
from app.api.app import create_app
from app.api.deps.auth import get_current_user
from app.application.ports.quest import QuestRankingCache, QuestRepository
from app.application.ports.rate_limit import RateLimiter
from app.application.ports.session import Session, SessionStore
from app.application.services.quest_ranking_service import QuestRankingService
from app.application.services.quest_service import QuestService
from app.domain.entities.user import User
from app.domain.quest.game import QUESTION_BY_ID, RankEntry
from app.infrastructure.db.quest_models import QuestRunModel
from app.infrastructure.db.repositories.quest import PgQuestRepository
from app.infrastructure.db.repositories.users import PgUserRepository
from dishka import Provider, Scope, make_async_container, provide
from sqlalchemy.ext.asyncio import AsyncSession


class _Limiter:
    async def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        return True


class _Cache:
    async def get(self, key: str) -> tuple[RankEntry, ...] | None:
        return None

    async def set(self, key: str, entries: tuple[RankEntry, ...], ttl: int) -> None:
        return None


class _Sessions:
    async def create(self, user_id: int, username: str | None) -> str | None:
        return None

    async def get(self, token: str) -> Session | None:
        return None


async def test_api_checks_auth_contract_and_server_rewards(session: AsyncSession) -> None:
    class TestProvider(Provider):
        scope = Scope.APP

        @provide
        def repository(self) -> QuestRepository:
            return PgQuestRepository(session)

        @provide
        def limiter(self) -> RateLimiter:
            return _Limiter()

        @provide
        def cache(self) -> QuestRankingCache:
            return _Cache()

        @provide
        def sessions(self) -> SessionStore:
            return _Sessions()

        quest = provide(QuestService)
        rankings = provide(QuestRankingService)

    container = make_async_container(TestProvider())
    app = create_app(container)
    user = await PgUserRepository(session).upsert(User(telegram_id=42))

    async def current_user() -> User:
        return user

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/api/quest/progress")).status_code == 422
        assert (await client.get("/api/quest/ranking")).status_code == 422
        assert (
            await client.get("/api/quest/progress", headers={"Authorization": "forged"})
        ).status_code == 401
        assert (
            await client.get("/api/quest/ranking", headers={"Authorization": "forged"})
        ).status_code == 401
        app.dependency_overrides[get_current_user] = current_user
        response = await client.get("/api/quest/progress")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        assert response.json()["total_xp"] == 0
        assert (await client.post("/api/quest/runs", json={"quest_id": "sky"})).status_code == 409
        run = (await client.post("/api/quest/runs", json={"quest_id": "forest"})).json()
        forged = await client.post(
            f"/api/quest/runs/{run['id']}/answer",
            json={"question_index": 0, "answer": "x", "points": 9999},
        )
        assert forged.status_code == 422
        model = await session.get(QuestRunModel, run["id"])
        assert model
        question_ids = list(model.question_ids)
        for index, question in enumerate(question_ids):
            result = await client.post(
                f"/api/quest/runs/{run['id']}/answer",
                json={"question_index": index, "answer": QUESTION_BY_ID[question].answer},
            )
            assert result.status_code == 200
        assert result.json()["progress"]["total_xp"] == 100
        assert result.json()["run"]["complete"]
        built = await client.post(
            "/api/quest/build", json={"building_id": "yurt", "target_level": 1}
        )
        assert built.status_code == 200 and built.json()["wood"] == 0
        assert (
            await client.post("/api/quest/build", json={"building_id": "well", "target_level": 1})
        ).status_code == 409
        ranking = (await client.get("/api/quest/ranking?period=week")).json()
        assert ranking["me"]["rank"] == 1 and ranking["me"]["points"] == 100
        assert "user_id" not in ranking["leaders"][0]
    await container.close()
