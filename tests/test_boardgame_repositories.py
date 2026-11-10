from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from app.application.services.boardgame_service import BoardGameService
from app.domain.boardgame.game import Action, Command, Outcome, Phase
from app.domain.entities.user import User
from app.domain.quest.game import RankingPeriod
from app.domain.subscription.weekly import week_start
from app.infrastructure.content.boardgame import load_board_catalog
from app.infrastructure.db.repositories.boardgame import PgRoomRepository
from app.infrastructure.db.repositories.quest import PgQuestRepository
from app.infrastructure.db.repositories.users import PgUserRepository
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.test_quest_rules import NOW

CATALOG = load_board_catalog(Path("web/public/boardgame/catalog.json"))


class FixedRandom:
    def below(self, maximum: int) -> int:
        return 0


class Events:
    def __init__(self) -> None:
        self.updates: list[tuple[str, int]] = []

    async def publish(self, code: str, revision: int) -> None:
        self.updates.append((code, revision))

    async def wait(self, code: str, revision: int, wait_seconds: int) -> None:
        return None


def service(session: AsyncSession) -> BoardGameService:
    return BoardGameService(PgRoomRepository(session), CATALOG, FixedRandom(), Events())


async def test_room_join_capacity_and_duplicate_purchase_are_locked(session: AsyncSession) -> None:
    for uid in (42, 43, 44, 45):
        await PgUserRepository(session).upsert(User(telegram_id=uid))
    game = service(session)
    room = await game.create(42, "Аян", "almaty_first")
    assert room
    added = await game.command(42, room.code, Command(0, Action.ADD_BOT, "balanced"), NOW)
    assert added.outcome == Outcome.APPLIED
    maker = async_sessionmaker(session.bind, expire_on_commit=False)

    async def join(uid: int) -> Outcome:
        async with maker() as independent:
            return (await service(independent).join(uid, f"Ойыншы {uid}", room.code, NOW)).outcome

    outcomes = await asyncio.gather(*(join(uid) for uid in (43, 44, 45)))
    assert outcomes.count(Outcome.APPLIED) == 2 and outcomes.count(Outcome.FULL) == 1
    session.expire_all()
    saved = await PgRoomRepository(session).get(room.code)
    assert saved and len(saved.room.seats) == 4 and len(saved.members) == 3
    assert await game.view(999, room.code) is None
    # Отдельная партия с ботом для конкурентного списания.
    room = await game.create(42, "Аян", "almaty_first")
    assert room
    await game.command(42, room.code, Command(0, Action.ADD_BOT, "balanced"), NOW)
    await game.command(42, room.code, Command(1, Action.START), NOW)
    await game.command(42, room.code, Command(2, Action.ROLL), NOW)

    async def buy() -> Outcome:
        async with maker() as independent:
            return (
                await service(independent).command(42, room.code, Command(3, Action.BUY), NOW)
            ).outcome

    results = await asyncio.gather(buy(), buy(), buy())
    assert results.count(Outcome.APPLIED) == 1 and results.count(Outcome.STALE) == 2
    session.expire_all()
    saved = await game.view(42, room.code)
    assert saved and saved.room.match and saved.room.match.players[0].cash == 1100
    assert saved.room.match.lots["2"].owner == 0


async def test_timeout_uses_server_clock_and_rewards_commit_once_per_scenario(
    session: AsyncSession,
) -> None:
    await PgUserRepository(session).upsert(User(telegram_id=42))
    game = service(session)
    room = await game.create(42, "Аян", "almaty_first")
    assert room
    await game.command(42, room.code, Command(0, Action.ADD_BOT, "balanced"), NOW)
    started = await game.command(42, room.code, Command(1, Action.START), NOW)
    assert started.record and started.record.deadline == NOW + timedelta(seconds=180)
    assert (
        await game.command(42, room.code, Command(2, Action.TIMEOUT), NOW)
    ).outcome == Outcome.TOO_EARLY
    timeout = await game.command(
        42, room.code, Command(2, Action.TIMEOUT), NOW + timedelta(seconds=181)
    )
    assert timeout.outcome == Outcome.APPLIED and timeout.record and timeout.record.room.match
    assert timeout.record.room.match.round == 2
    maker = async_sessionmaker(session.bind, expire_on_commit=False)
    for _ in range(2):
        # Готовим последнюю фазу двух разных комнат, не изменяя API-входы.
        if _:
            room = await game.create(42, "Аян", "almaty_first")
            assert room
            await game.command(42, room.code, Command(0, Action.ADD_BOT, "balanced"), NOW)
            await game.command(42, room.code, Command(1, Action.START), NOW)
        repo = PgRoomRepository(session)
        async with repo.locked(room.code) as saved:
            assert saved and saved.room.match
            match = saved.room.match
            players = (replace(match.players[0], cash=5000), replace(match.players[1], cash=100))
            final = replace(match, round=12, phase=Phase.END, players=players, turn=0)
            prepared = replace(saved, room=replace(saved.room, match=final))
            await repo.save(prepared, None, 0, week_start(NOW))

        async def finish(code: str, revision: int) -> Outcome:
            async with maker() as independent:
                return (
                    await service(independent).command(42, code, Command(revision, Action.END), NOW)
                ).outcome

        outcomes = await asyncio.gather(
            finish(room.code, prepared.room.revision), finish(room.code, prepared.room.revision)
        )
        assert outcomes.count(Outcome.APPLIED) == 1 and outcomes.count(Outcome.STALE) == 1
    session.expire_all()
    score = await PgQuestRepository(session).rank(42, RankingPeriod.ALL, week_start(NOW))
    assert score and score.points == 100
