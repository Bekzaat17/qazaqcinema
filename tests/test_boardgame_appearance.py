from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from app.api.routers.boardgame import AppearanceIn
from app.application.ports.boardgame import PlayerAppearance, RoomRecord
from app.application.services.boardgame_service import BoardGameService
from app.domain.boardgame.appearance import Portrait
from app.domain.boardgame.game import Action, Command, Outcome
from app.infrastructure.content.boardgame import load_board_catalog
from app.infrastructure.db.quest_models import BoardRoomModel
from app.infrastructure.db.repositories.boardgame import _dump, _record
from pydantic import ValidationError

_NOW = datetime(2026, 11, 11, 5, tzinfo=UTC)
_PHOTO = "https://t.me/i/userpic/320/example.jpg"


class _Rooms:
    def __init__(self) -> None:
        self.record: RoomRecord | None = None

    async def create(self, record: RoomRecord) -> None:
        self.record = record

    async def get(self, code: str) -> RoomRecord | None:
        return self.record

    @asynccontextmanager
    async def locked(self, code: str) -> AsyncIterator[RoomRecord | None]:
        yield self.record

    async def save(
        self, record: RoomRecord, winner_user_id: int | None, reward: int, week: date
    ) -> None:
        assert winner_user_id is None and reward == 0
        self.record = record


class _Random:
    def below(self, maximum: int) -> int:
        return 0


class _Events:
    def __init__(self) -> None:
        self.updates: list[int] = []

    async def publish(self, code: str, revision: int) -> None:
        self.updates.append(revision)

    async def wait(self, code: str, revision: int, wait_seconds: int) -> None:
        return None


@pytest.mark.parametrize(
    "url",
    [
        "https://other.example/avatar.jpg",
        "javascript:alert(1)",
        "http://t.me/i/userpic/x",
        "https://t.me.evil.test/i/userpic/x",
        "https://t.me@evil.test/i/userpic/x",
        "https://t.me/i/userpic/x#fragment",
    ],
)
def test_avatar_input_rejects_non_telegram_images(url: str) -> None:
    with pytest.raises(ValidationError):
        AppearanceIn(avatar_url=url)


def test_avatar_input_accepts_telegram_photo_and_explicit_portrait() -> None:
    value = AppearanceIn(avatar_url=_PHOTO, portrait=Portrait.FEMALE)
    assert value.avatar_url == _PHOTO and value.portrait == Portrait.FEMALE
    assert AppearanceIn().avatar_url == ""
    with pytest.raises(ValidationError):
        AppearanceIn.model_validate({"portrait": "guessed"})
    with pytest.raises(ValidationError):
        AppearanceIn.model_validate({"avatar_url": _PHOTO, "user_id": 999})


async def test_portraits_are_shared_by_seat_and_survive_the_storage_codec() -> None:
    rooms, events = _Rooms(), _Events()
    game = BoardGameService(
        rooms, load_board_catalog(Path("web/public/boardgame/catalog-v2.json")), _Random(), events
    )
    owner = PlayerAppearance(_PHOTO, Portrait.FEMALE)
    created = await game.create(42, "Аян", "almaty_first", owner)
    assert created
    assert created.appearances[created.members["42"]] == owner
    joined = await game.join(43, "Болат", created.code, _NOW, PlayerAppearance())
    assert joined.record
    record = joined.record
    model = BoardRoomModel(
        code=record.code, state=_dump(record), members=record.members, deadline=record.deadline
    )
    assert _record(model) == record
    legacy_state = _dump(record)
    legacy_state.pop("_appearances")
    model.state = legacy_state
    assert _record(model).appearances == {}
    assert _record(model).room == record.room

    # Обновить можно только свой портрет, а повтор не меняет версию и экономику.
    ready = await game.command(43, record.code, Command(record.room.revision, Action.READY), _NOW)
    assert ready.record
    started = await game.command(
        42, record.code, Command(ready.record.room.revision, Action.START), _NOW
    )
    assert started.record and started.record.room.match
    record = started.record
    before_room = record.room
    updated = await game.set_appearance(43, record.code, owner, _NOW)
    assert updated.record
    assert updated.record.room.revision == before_room.revision + 1
    assert updated.record.room.seats == before_room.seats
    assert updated.record.room.match == before_room.match
    assert updated.record.deadline == record.deadline
    assert updated.record.appearances[record.members["42"]] == owner
    assert updated.record.appearances[record.members["43"]] == owner
    again = await game.set_appearance(43, record.code, owner, _NOW)
    assert again.record == updated.record
    assert (await game.set_appearance(999, record.code, owner, _NOW)).outcome == Outcome.FORBIDDEN
