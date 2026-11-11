from __future__ import annotations

import re
from datetime import UTC, datetime
from urllib.parse import urlsplit

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.deps.auth import get_current_user
from app.application.ports.boardgame import (
    ActiveRoom,
    GameAccess,
    GameHistory,
    GameRanking,
    PlayerAppearance,
    PublicRoom,
    RoomRecord,
)
from app.application.ports.rate_limit import RateLimiter
from app.application.services.boardgame_service import BoardGameService, RoomResult
from app.domain.boardgame.appearance import Portrait
from app.domain.boardgame.game import Action, Catalog, Command, Outcome, Room
from app.domain.entities.user import User

router = APIRouter(prefix="/api/boardgame", tags=["boardgame"], route_class=DishkaRoute)


class AppearanceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    avatar_url: str = Field(default="", max_length=2048)
    portrait: Portrait = Portrait.MALE

    @field_validator("avatar_url")
    @classmethod
    def telegram_avatar(cls, value: str) -> str:
        if not value:
            return value
        url = urlsplit(value)
        if (
            url.scheme != "https"
            or url.netloc != "t.me"
            or not url.path.startswith("/i/userpic/")
            or url.fragment
        ):
            raise ValueError("invalid_telegram_avatar")
        return value


class PlayerIn(AppearanceIn):
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
    is_public: bool = Field(default=False, strict=True)


class VisibilityIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_public: bool = Field(strict=True)


class CommandIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0, strict=True)
    kind: Action
    target: str = Field(default="", max_length=48)
    tile: int = Field(default=-1, ge=-1, le=39, strict=True)
    amount: int = Field(default=0, ge=0, le=1000000, strict=True)
    give_tile: int = Field(default=-1, ge=-1, le=39, strict=True)


class RoomOut(BaseModel):
    blocked_seats: tuple[str, ...] = ()
    code: str
    room: Room
    me: str
    deadline: datetime | None
    server_time: datetime
    outcome: Outcome = Outcome.APPLIED
    appearances: dict[str, PlayerAppearance] = Field(default_factory=dict)
    is_public: bool = False


def _code(code: str) -> str:
    value = code.upper()
    if not re.fullmatch(r"[A-F0-9]{10}", value):
        raise HTTPException(404, "room_not_found")
    return value


def _out(
    record: RoomRecord,
    user_id: int,
    outcome: Outcome = Outcome.APPLIED,
    blocked_seats: tuple[str, ...] = (),
) -> RoomOut:
    return RoomOut(
        code=record.code,
        room=record.room,
        me=record.members[str(user_id)],
        deadline=record.deadline,
        server_time=datetime.now(UTC),
        outcome=outcome,
        appearances=record.appearances,
        is_public=record.is_public,
        blocked_seats=blocked_seats,
    )


def _result(result: RoomResult, user_id: int) -> RoomOut:
    if result.record is None:
        raise HTTPException(
            409 if result.outcome == Outcome.FULL else 404,
            "room_full" if result.outcome == Outcome.FULL else "room_not_available",
        )
    return _out(result.record, user_id, result.outcome, result.blocked_seats)


async def _limit(
    limiter: RateLimiter, user_id: int, scope: str, limit: int, seconds: int = 60
) -> None:
    if not await limiter.hit(f"boardgame:{scope}:{user_id}", limit, seconds):
        raise HTTPException(429, "too_many_requests")


@router.get("/catalog", response_model=Catalog)
async def catalog(definitions: FromDishka[Catalog], response: Response) -> Catalog:
    response.headers["Cache-Control"] = "public, max-age=300"
    return definitions


@router.get("/access", response_model=GameAccess)
async def access(
    service: FromDishka[BoardGameService],
    limiter: FromDishka[RateLimiter],
    response: Response,
    user: User = Depends(get_current_user),
) -> GameAccess:
    response.headers["Cache-Control"] = "private, no-store"
    await _limit(limiter, user.telegram_id, "access", 20)
    return await service.access(user.telegram_id)


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
    record = await service.create(
        user.telegram_id,
        body.name,
        body.scenario_id,
        PlayerAppearance(body.avatar_url, body.portrait),
        body.is_public,
    )
    if record is None:
        raise HTTPException(422, "invalid_scenario")
    return _out(record, user.telegram_id)


@router.get("/rooms", response_model=list[PublicRoom])
async def public_rooms(
    service: FromDishka[BoardGameService],
    limiter: FromDishka[RateLimiter],
    response: Response,
    user: User = Depends(get_current_user),
) -> list[PublicRoom]:
    response.headers["Cache-Control"] = "private, no-store"
    await _limit(limiter, user.telegram_id, "discover", 30)
    return await service.public_rooms(datetime.now(UTC))


@router.get("/history", response_model=list[GameHistory])
async def history(
    service: FromDishka[BoardGameService],
    response: Response,
    offset: int = 0,
    user: User = Depends(get_current_user),
) -> list[GameHistory]:
    response.headers["Cache-Control"] = "private, no-store"
    if not 0 <= offset <= 100000:
        raise HTTPException(422, "invalid_offset")
    return await service.history(user.telegram_id, offset)


@router.get("/rooms/mine", response_model=list[ActiveRoom])
async def my_rooms(
    service: FromDishka[BoardGameService],
    limiter: FromDishka[RateLimiter],
    response: Response,
    user: User = Depends(get_current_user),
) -> list[ActiveRoom]:
    response.headers["Cache-Control"] = "private, no-store"
    await _limit(limiter, user.telegram_id, "my_rooms", 30)
    return await service.my_rooms(user.telegram_id)


@router.get("/ranking", response_model=GameRanking)
async def game_ranking(
    service: FromDishka[BoardGameService],
    response: Response,
    user: User = Depends(get_current_user),
) -> GameRanking:
    response.headers["Cache-Control"] = "private, no-store"
    return await service.ranking(user.telegram_id)


@router.post("/rooms/{code}/visibility", response_model=RoomOut)
async def visibility(
    code: str,
    body: VisibilityIn,
    service: FromDishka[BoardGameService],
    limiter: FromDishka[RateLimiter],
    response: Response,
    user: User = Depends(get_current_user),
) -> RoomOut:
    response.headers["Cache-Control"] = "private, no-store"
    await _limit(limiter, user.telegram_id, "visibility", 12)
    return _result(
        await service.set_public(user.telegram_id, _code(code), body.is_public, datetime.now(UTC)),
        user.telegram_id,
    )


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
        await service.join(
            user.telegram_id,
            body.name,
            _code(code),
            datetime.now(UTC),
            PlayerAppearance(body.avatar_url, body.portrait),
        ),
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


@router.post("/rooms/{code}/appearance", response_model=RoomOut)
async def appearance(
    code: str,
    body: AppearanceIn,
    service: FromDishka[BoardGameService],
    limiter: FromDishka[RateLimiter],
    response: Response,
    user: User = Depends(get_current_user),
) -> RoomOut:
    response.headers["Cache-Control"] = "private, no-store"
    await _limit(limiter, user.telegram_id, "appearance", 12)
    return _result(
        await service.set_appearance(
            user.telegram_id,
            _code(code),
            PlayerAppearance(body.avatar_url, body.portrait),
            datetime.now(UTC),
        ),
        user.telegram_id,
    )
