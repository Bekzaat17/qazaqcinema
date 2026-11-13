"""Атомарность попыток и отсутствие автоматических разборов: настоящий PostgreSQL."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import cast

from app.application.ports.content import PostLogEntry
from app.domain.channel.content.item import ContentItem, QuizOpen
from app.domain.channel.content.kinds import ContentKind
from app.infrastructure.db.content_repositories import (
    PgContentRepository,
    PgPostLogRepository,
    PgQuizAnswerRepository,
)
from app.infrastructure.db.riddle_repositories import PgPublicationGate, PgRiddleAnswerRepository
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

_NOW = datetime(2026, 11, 13, 8, tzinfo=UTC)
_CLOSES = datetime(2026, 11, 13, 16, tzinfo=UTC)


async def _post(session: AsyncSession) -> PostLogEntry:
    items = PgContentRepository(session)
    await items.upsert_many([ContentItem(
        slug="riddle-test", kind=ContentKind.QUIZ_OPEN, topic="zhumbaq",
        title_kk="Жұмбақ", body_kk="", payload=QuizOpen("Сұрақ", ("Кірпі",)),
    )])
    item = await items.by_slug("riddle-test")
    assert item is not None and item.id is not None
    post = await PgPostLogRepository(session).add(PostLogEntry(
        slot_key="2026-11-13:jumbak", item_id=item.id, kind=item.kind,
        channel_message_id=101, posted_at=_NOW, quiz_closes_at=_CLOSES,
    ))
    assert post is not None
    return post


async def test_concurrent_wrong_answers_consume_at_most_three_attempts(
    session: AsyncSession,
) -> None:
    post = await _post(session)
    factory = async_sessionmaker(session.bind, expire_on_commit=False)

    async def answer() -> bool:
        async with factory() as connection:
            result = await PgRiddleAnswerRepository(connection).attempt(
                post.id or 0, 42, "Айгүл", "қоян", False, _NOW,
            )
            assert result.attempts <= 3
            return result.recorded

    recorded = await asyncio.gather(*(answer() for _ in range(12)))
    assert sum(recorded) == 3
    late = await PgRiddleAnswerRepository(session).attempt(
        post.id or 0, 42, "Айгүл", "кірпі", True, _NOW,
    )
    assert not late.recorded and not late.correct and late.attempts == 3


async def test_correct_answer_is_frozen_and_weekly_points_are_not_multiplied(
    session: AsyncSession,
) -> None:
    post = await _post(session)
    answers = PgRiddleAnswerRepository(session)
    await answers.attempt(post.id or 0, 42, "Айгүл", "қоян", False, _NOW)
    correct = await answers.attempt(post.id or 0, 42, "Айгүл", "кірпі", True, _NOW)
    assert correct.points == 2
    frozen = await answers.attempt(post.id or 0, 42, "Айгүл", "қоян", False, _NOW)
    assert not frozen.recorded and frozen.points == 2
    ranks = await answers.leaders(_NOW - timedelta(days=1), _NOW + timedelta(days=1))
    assert [(r.user_id, r.points, r.solved) for r in ranks] == [(42, 2, 1)]
    stats = await PgQuizAnswerRepository(session).stats(post.id or 0, 15)
    assert stats.total == 1 and stats.correct == 1


async def test_daily_riddle_is_omitted_from_automatic_results(session: AsyncSession) -> None:
    post = await _post(session)
    log = PgPostLogRepository(session)
    assert await log.by_slot_key(post.slot_key) == post
    assert await log.list_due_results(_CLOSES) == []


async def test_publication_gate_cannot_be_taken_twice_and_releases_on_exit(
    session: AsyncSession,
) -> None:
    gate = PgPublicationGate(cast(AsyncEngine, session.bind))
    async with gate.hold("test:jumbak") as first:
        assert first
        async with gate.hold("test:jumbak") as second:
            assert not second
    async with gate.hold("test:jumbak") as third:
        assert third
