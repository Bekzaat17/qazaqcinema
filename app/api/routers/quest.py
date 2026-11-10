from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.deps.auth import get_current_user
from app.api.schemas.quest import (
    AnswerIn,
    AnswerOut,
    BuildIn,
    ProgressOut,
    RankingOut,
    RankOut,
    RunOut,
    StartQuestIn,
)
from app.application.ports.rate_limit import RateLimiter
from app.application.services.quest_ranking_service import QuestRankingService
from app.application.services.quest_service import QuestService
from app.domain.entities.user import User
from app.domain.quest.game import AnswerOutcome, BuildOutcome, RankingPeriod

router = APIRouter(prefix="/api/quest", tags=["quest"], route_class=DishkaRoute)


async def _limit(limiter: RateLimiter, user_id: int, scope: str, limit: int) -> None:
    if not await limiter.hit(f"quest:{scope}:{user_id}", limit, 60):
        raise HTTPException(429, "too_many_requests")


@router.get("/progress", response_model=ProgressOut)
async def progress(
    service: FromDishka[QuestService],
    limiter: FromDishka[RateLimiter],
    response: Response,
    user: User = Depends(get_current_user),
) -> ProgressOut:
    response.headers["Cache-Control"] = "private, no-store"
    await _limit(limiter, user.telegram_id, "read", 30)
    return ProgressOut.of(await service.progress(user.telegram_id, datetime.now(UTC)))


@router.post("/runs", response_model=RunOut)
async def start_run(
    body: StartQuestIn,
    service: FromDishka[QuestService],
    limiter: FromDishka[RateLimiter],
    user: User = Depends(get_current_user),
) -> RunOut:
    await _limit(limiter, user.telegram_id, "write", 30)
    run = await service.start(user.telegram_id, body.quest_id, datetime.now(UTC))
    if run is None:
        raise HTTPException(409, "quest_locked")
    return RunOut.of(run)


@router.post("/runs/{run_id}/answer", response_model=AnswerOut)
async def answer(
    run_id: UUID,
    body: AnswerIn,
    service: FromDishka[QuestService],
    limiter: FromDishka[RateLimiter],
    user: User = Depends(get_current_user),
) -> AnswerOut:
    await _limit(limiter, user.telegram_id, "answer", 60)
    now = datetime.now(UTC)
    result = await service.answer(
        user.telegram_id, str(run_id), body.question_index, body.answer, now
    )
    if result is None:
        raise HTTPException(404, "quest_run_not_found")
    if result.outcome == AnswerOutcome.EXPIRED:
        raise HTTPException(409, "quest_run_expired")
    if result.outcome == AnswerOutcome.INVALID:
        raise HTTPException(422, "quest_invalid_answer")
    return AnswerOut(
        run=RunOut.of(result.run),
        outcome=result.outcome,
        explanation=result.explanation,
        progress=ProgressOut.of(await service.progress(user.telegram_id, now)),
    )


@router.post("/build", response_model=ProgressOut)
async def build(
    body: BuildIn,
    service: FromDishka[QuestService],
    limiter: FromDishka[RateLimiter],
    user: User = Depends(get_current_user),
) -> ProgressOut:
    await _limit(limiter, user.telegram_id, "write", 30)
    result = await service.build(user.telegram_id, body.building_id, body.target_level)
    if result == BuildOutcome.INSUFFICIENT:
        raise HTTPException(409, "quest_not_enough_materials")
    if result == BuildOutcome.INVALID:
        raise HTTPException(422, "quest_invalid_building")
    return ProgressOut.of(await service.progress(user.telegram_id, datetime.now(UTC)))


@router.get("/ranking", response_model=RankingOut)
async def ranking(
    service: FromDishka[QuestRankingService],
    limiter: FromDishka[RateLimiter],
    response: Response,
    period: RankingPeriod = RankingPeriod.WEEK,
    user: User = Depends(get_current_user),
) -> RankingOut:
    response.headers["Cache-Control"] = "private, no-store"
    await _limit(limiter, user.telegram_id, "ranking", 12)
    now = datetime.now(UTC)
    leaders = await service.leaders(period, now)
    me = await service.rank(user.telegram_id, period, now)
    return RankingOut(
        leaders=[RankOut.of(row, user.telegram_id) for row in leaders],
        me=RankOut.of(me, user.telegram_id) if me else None,
    )
