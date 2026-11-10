from __future__ import annotations

import asyncio
from datetime import timedelta

from app.application.services.quest_service import QuestService
from app.domain.entities.user import User
from app.domain.quest.game import QUESTION_BY_ID, AnswerOutcome, BuildOutcome, RankingPeriod
from app.domain.subscription.weekly import week_start
from app.infrastructure.db.repositories.quest import PgQuestChannelStore, PgQuestRepository
from app.infrastructure.db.repositories.users import PgUserRepository
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.test_quest_rules import NOW


async def _player(session: AsyncSession, user_id: int = 42) -> QuestService:
    await PgUserRepository(session).upsert(User(telegram_id=user_id))
    return QuestService(PgQuestRepository(session))


async def test_rewards_are_atomic_daily_and_owned_by_authenticated_user(
    session: AsyncSession,
) -> None:
    service = await _player(session)
    assert await service.start(42, "river", NOW) is None
    run = await service.start(42, "forest", NOW)
    assert run is not None
    assert (await service.start(42, "forest", NOW)) == run
    assert await service.answer(999, run.id, 0, "Орман", NOW) is None
    for index, question in enumerate(run.question_ids):
        result = await service.answer(42, run.id, index, QUESTION_BY_ID[question].answer, NOW)
        assert result and result.outcome == AnswerOutcome.CORRECT
    progress = await service.progress(42, NOW)
    assert (progress.total_xp, progress.wood, progress.stone) == (100, 25, 15)
    assert progress.completed_today == ("forest",)
    await service.answer(42, run.id, 2, QUESTION_BY_ID[run.question_ids[-1]].answer, NOW)
    assert (await service.progress(42, NOW)).total_xp == 100
    assert await service.start(42, "river", NOW) is not None
    tomorrow = await service.start(42, "forest", NOW + timedelta(days=1))
    assert tomorrow and tomorrow.id != run.id
    assert not (await service.progress(42, NOW + timedelta(days=1))).completed_today


async def test_concurrent_final_answer_awards_once_and_build_spends_once(
    session: AsyncSession,
) -> None:
    service = await _player(session)
    run = await service.start(42, "forest", NOW)
    assert run
    for index in (0, 1):
        await service.answer(42, run.id, index, QUESTION_BY_ID[run.question_ids[index]].answer, NOW)
    maker = async_sessionmaker(session.bind, expire_on_commit=False)

    async def finish() -> None:
        async with maker() as independent:
            await QuestService(PgQuestRepository(independent)).answer(
                42,
                run.id,
                2,
                QUESTION_BY_ID[run.question_ids[2]].answer,
                NOW,
            )

    await asyncio.gather(finish(), finish(), finish())
    session.expire_all()
    progress = await service.progress(42, NOW)
    assert (progress.total_xp, progress.wood, progress.stone) == (100, 25, 15)

    async def build() -> BuildOutcome:
        async with maker() as independent:
            return await QuestService(PgQuestRepository(independent)).build(42, "yurt", 1)

    # Закрываем read-транзакцию основной сессии перед независимыми писателями.
    await session.commit()
    outcomes = await asyncio.gather(build(), build())
    assert sorted(outcomes) == sorted((BuildOutcome.BUILT, BuildOutcome.REPLAY))
    session.expire_all()
    progress = await service.progress(42, NOW)
    assert (progress.wood, progress.stone, dict(progress.buildings)) == (0, 5, {"yurt": 1})


async def test_rankings_keep_total_xp_when_week_changes_and_break_ties_consistently(
    session: AsyncSession,
) -> None:
    for user_id in (51, 42):
        service = await _player(session, user_id)
        run = await service.start(user_id, "forest", NOW)
        assert run
        for index, question in enumerate(run.question_ids):
            await service.answer(user_id, run.id, index, QUESTION_BY_ID[question].answer, NOW)
    repo = PgQuestRepository(session)
    week = week_start(NOW)
    entries = await repo.leaders(RankingPeriod.WEEK, week, 10)
    assert [(e.user_id, e.rank, e.points) for e in entries] == [(42, 1, 100), (51, 2, 100)]
    assert (await repo.rank(51, RankingPeriod.WEEK, week)) == entries[1]
    assert await repo.leaders(RankingPeriod.WEEK, week + timedelta(days=7), 10) == ()
    assert len(await repo.leaders(RankingPeriod.ALL, week + timedelta(days=7), 10)) == 2
    assert await repo.rank(99, RankingPeriod.ALL, week) is None


async def test_channel_delivery_reservation_survives_restarts(session: AsyncSession) -> None:
    store = PgQuestChannelStore(session)
    key = "test:2026-11-09:live"
    assert await store.reserve(key)
    assert not await store.reserve(key)
    assert await store.message_id(key) is None
    await store.delivered(key, 123)
    assert await PgQuestChannelStore(session).message_id(key) == 123
