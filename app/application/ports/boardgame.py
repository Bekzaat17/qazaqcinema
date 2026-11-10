from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from app.domain.boardgame.game import Room


@dataclass(frozen=True, slots=True)
class RoomRecord:
    code: str
    room: Room
    members: dict[str, str]
    deadline: datetime | None = None


class RoomRepository(Protocol):
    async def create(self, record: RoomRecord) -> None: ...
    async def get(self, code: str) -> RoomRecord | None: ...
    def locked(self, code: str) -> AbstractAsyncContextManager[RoomRecord | None]: ...
    async def save(
        self, record: RoomRecord, winner_user_id: int | None, reward: int, week: date
    ) -> None: ...


class GameRandom(Protocol):
    def below(self, maximum: int) -> int: ...


class RoomEvents(Protocol):
    async def publish(self, code: str, revision: int) -> None: ...
    async def wait(self, code: str, revision: int, wait_seconds: int) -> None: ...
