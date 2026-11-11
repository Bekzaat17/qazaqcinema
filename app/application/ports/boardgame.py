from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol

from app.domain.boardgame.appearance import Portrait
from app.domain.boardgame.game import Room


@dataclass(frozen=True, slots=True)
class PlayerAppearance:
    avatar_url: str = ""
    portrait: Portrait = Portrait.MALE


@dataclass(frozen=True, slots=True)
class RoomRecord:
    code: str
    room: Room
    members: dict[str, str]
    deadline: datetime | None = None
    appearances: dict[str, PlayerAppearance] = field(default_factory=dict)
    is_public: bool = False


@dataclass(frozen=True, slots=True)
class PublicRoom:
    code: str
    host_name: str
    scenario_id: str
    players: int


@dataclass(frozen=True, slots=True)
class ActiveRoom(PublicRoom):
    started: bool
    is_public: bool


@dataclass(frozen=True, slots=True)
class ResultPlayer:
    user_id: int
    name: str
    capital: int
    won: bool


@dataclass(frozen=True, slots=True)
class CompletedGame:
    code: str
    scenario_id: str
    board_id: str
    rounds: int
    finished_at: datetime
    winner_name: str
    player_count: int
    players: tuple[ResultPlayer, ...]


@dataclass(frozen=True, slots=True)
class GameHistory:
    code: str
    scenario_id: str
    board_id: str
    rounds: int
    finished_at: datetime
    winner_name: str
    player_count: int
    capital: int
    won: bool


@dataclass(frozen=True, slots=True)
class GameRank:
    rank: int
    name: str
    played: int
    wins: int
    is_me: bool


@dataclass(frozen=True, slots=True)
class GameRanking:
    entries: tuple[GameRank, ...]
    me: GameRank | None


@dataclass(frozen=True, slots=True)
class GameAccess:
    games_started: int
    free_left: int
    allowed: bool
    channel_url: str


class RoomRepository(Protocol):
    def lock_players(self, user_ids: tuple[int, ...]) -> AbstractAsyncContextManager[None]: ...
    async def games_started(self, user_id: int) -> int: ...
    async def create(self, record: RoomRecord) -> None: ...
    async def get(self, code: str) -> RoomRecord | None: ...
    async def public_rooms(self, now: datetime) -> list[RoomRecord]: ...
    async def my_rooms(self, user_id: int) -> list[RoomRecord]: ...
    async def touch_lobby(self, code: str, now: datetime) -> None: ...
    async def complete(self, game: CompletedGame) -> None: ...
    async def history(self, user_id: int, offset: int) -> list[GameHistory]: ...
    async def ranking(self, user_id: int) -> GameRanking: ...
    def locked(self, code: str) -> AbstractAsyncContextManager[RoomRecord | None]: ...
    async def save(
        self, record: RoomRecord, winner_user_id: int | None, reward: int, week: date
    ) -> None: ...


class GameRandom(Protocol):
    def below(self, maximum: int) -> int: ...


class RoomEvents(Protocol):
    async def publish(self, code: str, revision: int) -> None: ...
    async def wait(self, code: str, revision: int, wait_seconds: int) -> None: ...
