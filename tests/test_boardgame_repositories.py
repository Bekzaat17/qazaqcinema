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


async def test_four_people_reconnect_and_finish_after_concurrent_commands(
    session: AsyncSession,
) -> None:
    ids = (42, 43, 44, 45)
    for uid in ids:
        await PgUserRepository(session).upsert(User(telegram_id=uid))
    game = service(session)
    created = await game.create(42, "Аян", "almaty_first")
    assert created
    maker = async_sessionmaker(session.bind, expire_on_commit=False)

    async def join(uid: int) -> Outcome:
        async with maker() as independent:
            return (await service(independent).join(uid, str(uid), created.code, NOW)).outcome

    assert await asyncio.gather(*(join(uid) for uid in ids[1:])) == [Outcome.APPLIED] * 3

    async def command(uid: int, action: Action, revision: int) -> Outcome:
        async with maker() as independent:
            result = await service(independent).command(
                uid, created.code, Command(revision, action), NOW
            )
            return result.outcome

    ready = await asyncio.gather(*(command(uid, Action.READY, 3) for uid in ids[1:]))
    assert ready.count(Outcome.APPLIED) == 1 and ready.count(Outcome.STALE) == 2
    for uid, outcome in zip(ids[1:], ready, strict=True):
        if outcome == Outcome.STALE:
            current = await game.view(42, created.code)
            assert current
            assert await command(uid, Action.READY, current.room.revision) == Outcome.APPLIED
    current = await game.view(42, created.code)
    assert current
    started = await game.command(
        42, created.code, Command(current.room.revision, Action.START), NOW
    )
    assert started.record
    revision = started.record.room.revision
    duplicates = await asyncio.gather(*(command(42, Action.ROLL, revision) for _ in range(3)))
    assert duplicates.count(Outcome.APPLIED) == 1 and duplicates.count(Outcome.STALE) == 2
    # Каждый запрос создаёт новый сервис и сессию: продолжение не зависит от памяти API.
    now = NOW
    for _ in range(60):
        async with maker() as independent:
            resumed = service(independent)
            current = await resumed.view(43, created.code)
            assert current and current.room.match
            if current.room.match.phase == Phase.FINISHED:
                break
            now += timedelta(seconds=181)
            result = await resumed.command(
                43, created.code, Command(current.room.revision, Action.TIMEOUT), now
            )
            assert result.outcome == Outcome.APPLIED
    assert current and current.room.match and current.room.match.phase == Phase.FINISHED
    for uid in ids:
        async with maker() as independent:
            observed = await service(independent).view(uid, created.code)
            assert observed and observed.room == current.room
