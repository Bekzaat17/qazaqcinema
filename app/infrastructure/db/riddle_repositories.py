"""PostgreSQL: лок публикации без TTL и атомарные попытки жұмбақ дня."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from hashlib import blake2b

from sqlalchemy import func, select, text as sql_text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.application.ports.riddles import RiddleAttempt, RiddleRank
from app.domain.channel.content.daily_riddle import MAX_ATTEMPTS
from app.infrastructure.db.models import ChannelPostLogModel, QuizAnswerModel


class PgPublicationGate:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    @asynccontextmanager
    async def hold(self, key: str) -> AsyncIterator[bool]:
        # Отдельное соединение: коммиты репозиториев не отпускают лок посреди отправки.
        lock_id = int.from_bytes(blake2b(key.encode(), digest_size=8).digest(), signed=True)
        async with self._engine.begin() as connection:
            acquired = await connection.scalar(
                sql_text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": lock_id},
            )
            yield bool(acquired)


class PgRiddleAnswerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def attempt(
        self, post_id: int, user_id: int, name: str, text: str, correct: bool, at: datetime,
    ) -> RiddleAttempt:
        stmt = pg_insert(QuizAnswerModel).values(
            post_id=post_id, user_id=user_id, first_name=name[:128], text=text[:255],
            is_correct=correct, answered_at=at, attempt_count=1,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_quiz_answers_post_user",
            set_={
                "first_name": stmt.excluded.first_name, "text": stmt.excluded.text,
                "is_correct": correct, "answered_at": at,
                "attempt_count": QuizAnswerModel.attempt_count + 1,
            },
            where=(
                QuizAnswerModel.is_correct.is_(False)
                & (QuizAnswerModel.attempt_count < MAX_ATTEMPTS)
            ),
        ).returning(QuizAnswerModel.attempt_count, QuizAnswerModel.is_correct)
        row = (await self._session.execute(stmt)).one_or_none()
        if row is not None:
            await self._session.commit()
            return RiddleAttempt(int(row[0]), bool(row[1]), True)
        existing = (await self._session.execute(
            select(QuizAnswerModel.attempt_count, QuizAnswerModel.is_correct).where(
                QuizAnswerModel.post_id == post_id, QuizAnswerModel.user_id == user_id,
            ),
        )).one()
        await self._session.commit()
        return RiddleAttempt(int(existing[0]), bool(existing[1]), False)

    async def leaders(self, since: datetime, until: datetime) -> list[RiddleRank]:
        points = func.sum(MAX_ATTEMPTS + 1 - QuizAnswerModel.attempt_count)
        stmt = (
            select(
                QuizAnswerModel.user_id, func.max(QuizAnswerModel.first_name),
                points, func.count(),
            )
            .join(ChannelPostLogModel, ChannelPostLogModel.id == QuizAnswerModel.post_id)
            .where(
                ChannelPostLogModel.slot_key.endswith(":jumbak"),
                ChannelPostLogModel.posted_at >= since,
                ChannelPostLogModel.posted_at < until,
                QuizAnswerModel.is_correct.is_(True),
            )
            .group_by(QuizAnswerModel.user_id)
            .order_by(points.desc(), QuizAnswerModel.user_id)
        )
        return [RiddleRank(int(uid), name, int(score), int(solved))
                for uid, name, score, solved in await self._session.execute(stmt)]
