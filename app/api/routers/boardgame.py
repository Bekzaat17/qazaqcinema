from __future__ import annotations

import re
from datetime import UTC, datetime

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.deps.auth import get_current_user
from app.application.ports.boardgame import RoomRecord
from app.application.ports.rate_limit import RateLimiter
from app.application.services.boardgame_service import BoardGameService, RoomResult
from app.domain.boardgame.game import Action, Catalog, Command, Outcome, Room
from app.domain.entities.user import User

router = APIRouter(prefix="/api/boardgame", tags=["boardgame"], route_class=DishkaRoute)


class PlayerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=24)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError("invalid_name")
        return value


class CreateIn(PlayerIn):
    scenario_id: str = Field(min_length=1, max_length=48)


class CommandIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0, strict=True)
    kind: Action
    target: str = Field(default="", max_length=48)
    tile: int = Field(default=-1, ge=-1, le=39, strict=True)
    amount: int = Field(default=0, ge=0, le=1000000, strict=True)


class RoomOut(BaseModel):
    code: str
    room: Room
    me: str
    deadline: datetime | None
    server_time: datetime
    outcome: Outcome = Outcome.APPLIED


def _code(code: str) -> str:
    value = code.upper()
    if not re.fullmatch(r"[A-F0-9]{10}", value):
        raise HTTPException(404, "room_not_found")
    return value


def _out(record: RoomRecord, user_id: int, outcome: Outcome = Outcome.APPLIED) -> RoomOut:
    return RoomOut(
        code=record.code,
        room=record.room,
        me=record.members[str(user_id)],
        deadline=record.deadline,
        server_time=datetime.now(UTC),
        outcome=outcome,
    )


def _result(result: RoomResult, user_id: int) -> RoomOut:
    if result.record is None:
        raise HTTPException(
            409 if result.outcome == Outcome.FULL else 404,
            "room_full" if result.outcome == Outcome.FULL else "room_not_available",
        )
    return _out(result.record, user_id, result.outcome)


async def _limit(
    limiter: RateLimiter, user_id: int, scope: str, limit: int, seconds: int = 60
) -> None:
    if not await limiter.hit(f"boardgame:{scope}:{user_id}", limit, seconds):
        raise HTTPException(429, "too_many_requests")


@router.get("/catalog", response_model=Catalog)
async def catalog(definitions: FromDishka[Catalog], response: Response) -> Catalog:
    response.headers["Cache-Control"] = "public, max-age=300"
    return definitions


@router.post("/rooms", response_model=RoomOut)
async def create(
    body: CreateIn,
    service: FromDishka[BoardGameService],
    limiter: FromDishka[RateLimiter],
    response: Response,
    user: User = Depends(get_current_user),
) -> RoomOut:
    response.headers["Cache-Control"] = "private, no-store"
    await _limit(limiter, user.telegram_id, "create", 6, 3600)
    record = await service.create(user.telegram_id, body.name, body.scenario_id)
    if record is None:
        raise HTTPException(422, "invalid_scenario")
    return _out(record, user.telegram_id)


@router.post("/rooms/{code}/join", response_model=RoomOut)
async def join(
    code: str,
    body: PlayerIn,
    service: FromDishka[BoardGameService],
    limiter: FromDishka[RateLimiter],
    response: Response,
    user: User = Depends(get_current_user),
) -> RoomOut:
    response.headers["Cache-Control"] = "private, no-store"
    await _limit(limiter, user.telegram_id, "join", 12)
    return _result(
        await service.join(user.telegram_id, body.name, _code(code), datetime.now(UTC)),
        user.telegram_id,
    )


@router.get("/rooms/{code}", response_model=RoomOut)
async def view(
    code: str,
    service: FromDishka[BoardGameService],
    limiter: FromDishka[RateLimiter],
    response: Response,
    after: int | None = None,
    user: User = Depends(get_current_user),
) -> RoomOut:
    response.headers["Cache-Control"] = "private, no-store"
    await _limit(limiter, user.telegram_id, "read", 90)
    record = await service.view(user.telegram_id, _code(code), after)
    if record is None:
        raise HTTPException(404, "room_not_found")
    return _out(record, user.telegram_id)


@router.post("/rooms/{code}/command", response_model=RoomOut)
async def command(
    code: str,
    body: CommandIn,
    service: FromDishka[BoardGameService],
    limiter: FromDishka[RateLimiter],
    response: Response,
    user: User = Depends(get_current_user),
) -> RoomOut:
    response.headers["Cache-Control"] = "private, no-store"
    await _limit(limiter, user.telegram_id, "command", 90)
    return _result(
        await service.command(
            user.telegram_id, _code(code), Command(**body.model_dump()), datetime.now(UTC)
        ),
        user.telegram_id,
    )


@router.post("/rooms/{code}/leave", response_model=dict[str, bool])
async def leave(
    code: str,
    service: FromDishka[BoardGameService],
    response: Response,
    user: User = Depends(get_current_user),
) -> dict[str, bool]:
    response.headers["Cache-Control"] = "private, no-store"
    result = await service.leave(user.telegram_id, _code(code), datetime.now(UTC))
    if result.outcome != Outcome.APPLIED:
        raise HTTPException(409, "room_already_started")
    return {"ok": True}
