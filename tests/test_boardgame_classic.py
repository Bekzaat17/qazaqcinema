from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path

import pytest
from app.domain.boardgame.game import (
    Action,
    ClassicState,
    Command,
    Debt,
    Lot,
    Outcome,
    Phase,
    Room,
    Seat,
    apply_command,
    auto_turn,
    board_for,
    rent_for,
)
from app.domain.boardgame.validation import validate_catalog
from app.infrastructure.content.boardgame import load_board_catalog

CATALOG = load_board_catalog(Path("web/public/boardgame/catalog.json"))


def started() -> Room:
    room = Room(
        0,
        "human",
        CATALOG.scenarios[0].id,
        (
            Seat("human", "Аян", "#479e8b", ready=True),
            Seat("other", "Айша", "#d6a854", ready=True),
        ),
    )
    return apply_command(CATALOG, room, "human", Command(0, Action.START), lambda n: 0).room


def change(room: Room, **changes: object) -> Room:
    assert room.match
    return replace(room, match=replace(room.match, **changes))


def send(room: Room, kind: Action, actor: str = "human", **kwargs: object) -> Room:
    result = apply_command(
        CATALOG, room, actor, Command(room.revision, kind, **kwargs), lambda n: 0
    )
    assert result.outcome == Outcome.APPLIED
    return result.room


def test_classic_layout_groups_and_archive() -> None:
    validate_catalog(CATALOG)
    for board in CATALOG.boards:
        assert len(board.tiles) == 40
        assert [board.tiles[i].kind for i in (0, 10, 20, 30)] == [
            "start",
            "jail",
            "parking",
            "go_to_jail",
        ]
        assert [i for i, t in enumerate(board.tiles) if t.kind == "station"] == [5, 15, 25, 35]
        groups = Counter(t.group for t in board.tiles if t.kind == "property")
        assert sorted(groups.values()) == [2, 2, 3, 3, 3, 3, 3, 3]
        for group in groups:
            assert len({t.color for t in board.tiles if t.group == group}) == 1
        assert all(len(t.rents) == 6 for t in board.tiles if t.kind == "property")
    archived = replace(started(), scenario_id="almaty_first", match=None)
    archived = send(archived, Action.START)
    assert len(board_for(CATALOG, archived).tiles) == 24
    assert archived.match and archived.match.classic is None


def test_utilities_and_four_stations() -> None:
    room = started()
    assert room.match
    match = replace(room.match, dice=(3, 4), lots={"12": Lot(1), "5": Lot(1)})
    board = board_for(CATALOG, room)
    assert rent_for(board, match, 12) == 28
    match = replace(
        match, lots={**match.lots, "28": Lot(1), "15": Lot(1), "25": Lot(1), "35": Lot(1)}
    )
    assert rent_for(board, match, 12) == 70
    assert rent_for(board, match, 5) == 200


def test_three_doubles_send_to_jail_without_salary() -> None:
    room = started()
    assert room.match
    players = (replace(room.match.players[0], position=39), room.match.players[1])
    room = change(room, players=players, classic=ClassicState(doubles=2))
    rolled = send(room, Action.ROLL)
    assert rolled.match and rolled.match.players[0].position == 10
    assert rolled.match.players[0].cash == 1500
    assert rolled.match.classic and rolled.match.classic.jailed == {"0": 0}
    ended = send(rolled, Action.END)
    assert ended.match and ended.match.turn == 1


def test_jail_double_releases_without_extra_turn_and_bail_preserves_roll() -> None:
    room = started()
    assert room.match
    room = change(
        room,
        players=(replace(room.match.players[0], position=10), room.match.players[1]),
        classic=ClassicState({"0": 0}),
    )
    released = send(room, Action.ROLL)
    assert released.match and released.match.players[0].position == 12
    assert (
        released.match.classic
        and not released.match.classic.jailed
        and not released.match.classic.doubles
    )
    released = send(released, Action.PASS)
    assert send(released, Action.END).match.turn == 1
    bailed = send(room, Action.BAIL)
    assert (
        bailed.match and bailed.match.phase == Phase.ROLL and bailed.match.players[0].cash == 1450
    )


def test_negotiated_swap_is_atomic_and_requires_recipient_consent() -> None:
    room = change(started(), lots={"1": Lot(0), "6": Lot(1)})
    room = send(room, Action.ASK, target="other", tile=1, amount=100, give_tile=6)
    assert room.match
    first = room.match.offers[0]
    forbidden = apply_command(
        CATALOG, room, "human", Command(room.revision, Action.ACCEPT, first.id), lambda n: 0
    )
    assert forbidden.outcome == Outcome.FORBIDDEN
    room = send(room, Action.COUNTER, actor="other", target=first.id, amount=50, give_tile=6)
    assert room.match and room.match.lots["1"].owner == 0
    offer = room.match.offers[0]
    before = room
    room = send(room, Action.ACCEPT, target=offer.id)
    assert room.match and room.match.lots["1"].owner == 1 and room.match.lots["6"].owner == 0
    assert [p.cash for p in room.match.players] == [1550, 1450]
    retry = apply_command(
        CATALOG, room, "human", Command(before.revision, Action.ACCEPT, offer.id), lambda n: 0
    )
    assert retry.outcome == Outcome.STALE
    room = send(room, Action.OFFER, tile=1, amount=60)
    assert room.match
    room = send(room, Action.WITHDRAW, target=room.match.offers[0].id)
    assert room.match and not room.match.offers


def test_changed_ownership_invalidates_offer_without_spending() -> None:
    room = change(started(), lots={"1": Lot(0), "6": Lot(1)})
    room = send(room, Action.OFFER, actor="other", tile=1, amount=100)
    assert room.match
    offer = room.match.offers[0]
    room = change(room, lots={"1": Lot(0, mortgaged=True), "6": Lot(1)})
    result = apply_command(
        CATALOG, room, "human", Command(room.revision, Action.ACCEPT, offer.id), lambda n: 0
    )
    assert result.outcome == Outcome.INVALID and result.room == room


@pytest.mark.parametrize(
    "game", json.loads(Path("tests/fixtures/boardgame_classic_contract.json").read_text())["games"]
)
def test_classic_contract(game: dict[str, object]) -> None:
    room = Room(0, "human", str(game["scenario"]), (Seat("human", "Аян", "#479e8b", ready=True),))
    count = 0

    def random(n: int) -> int:
        nonlocal count
        result = (count * 17 + 7) % n
        count += 1
        return result

    for bot in ("balanced", "builder"):
        room = apply_command(
            CATALOG, room, "human", Command(room.revision, Action.ADD_BOT, bot), random
        ).room
    room = apply_command(CATALOG, room, "human", Command(room.revision, Action.START), random).room
    for _ in range(int(str(game["steps"]))):
        room = auto_turn(CATALOG, room, random)
    assert room.match and room.match.phase == Phase.FINISHED
    assert all(p.cash >= 0 for p in room.match.players)
    digest = sha256(
        json.dumps(asdict(room), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    assert digest == game["hash"]


def test_third_failed_jail_roll_settles_debt_before_moving() -> None:
    room = started()
    assert room.match
    room = change(
        room,
        players=(replace(room.match.players[0], position=10, cash=40), room.match.players[1]),
        lots={"1": Lot(0)},
        classic=ClassicState({"0": 2}),
    )
    dice = iter((0, 1))
    room = apply_command(
        CATALOG, room, "human", Command(room.revision, Action.ROLL), lambda n: next(dice)
    ).room
    assert room.match and room.match.phase == Phase.DEBT
    assert room.match.players[0].position == 10
    assert room.match.classic and room.match.classic.release_steps == 3
    room = send(room, Action.MORTGAGE, tile=1)
    room = send(room, Action.SETTLE)
    assert room.match and room.match.players[0].position == 13
    assert room.match.players[0].cash == 20
    assert room.match.classic and not room.match.classic.release_steps


def test_classic_building_needs_complete_group_and_even_four_houses() -> None:
    room = change(started(), lots={"6": Lot(0), "8": Lot(0)})
    result = apply_command(
        CATALOG, room, "human", Command(room.revision, Action.BUILD, tile=6), lambda n: 0
    )
    assert result.outcome == Outcome.GROUP_REQUIRED
    room = change(room, lots={"6": Lot(0, 4), "8": Lot(0, 4), "9": Lot(0, 3)})
    result = apply_command(
        CATALOG, room, "human", Command(room.revision, Action.BUILD, tile=6), lambda n: 0
    )
    assert result.outcome == Outcome.EVEN_BUILDING
    room = send(room, Action.BUILD, tile=9)
    room = send(room, Action.BUILD, tile=6)
    assert room.match and room.match.lots["6"].level == 5


def test_unlimited_passes_round_100_and_only_last_survivor_wins() -> None:
    room = replace(started(), scenario_id="almaty_classic_unlimited")
    room = change(room, turn=1, round=100, phase=Phase.END)
    room = send(room, Action.END, actor="other")
    assert room.match and room.match.round == 101 and room.match.phase == Phase.ROLL
    room = change(
        room,
        phase=Phase.DEBT,
        debt=Debt(50),
        players=(replace(room.match.players[0], cash=0), room.match.players[1]),
    )
    room = send(room, Action.BANKRUPT)
    assert room.match and room.match.phase == Phase.FINISHED and room.match.winner == 1


def test_unlimited_bot_batch_does_not_invent_a_winner() -> None:
    room = replace(started(), scenario_id="turkistan_classic_unlimited")
    assert room.match
    bot = replace(room.match.players[1], bot="balanced", cash=1000000)
    third = replace(bot, id="third", name="Bot", bot="builder")
    room = replace(room, seats=(*room.seats, Seat("third", "Bot", "#d6a854", "builder", True)))
    room = change(
        room,
        turn=1,
        round=1000,
        players=(replace(room.match.players[0], bankrupt=True, cash=0), bot, third),
    )
    advanced = auto_turn(CATALOG, room, lambda n: 0)
    assert advanced.match and advanced.match.phase != Phase.FINISHED
    assert advanced.match.round > 1000 and advanced.match.winner == -1


def test_both_cities_keep_the_exact_classic_40_space_order() -> None:
    expected = (
        "start",
        "property",
        "community",
        "property",
        "tax",
        "station",
        "property",
        "chance",
        "property",
        "property",
        "jail",
        "property",
        "utility",
        "property",
        "property",
        "station",
        "property",
        "community",
        "property",
        "property",
        "parking",
        "property",
        "chance",
        "property",
        "property",
        "station",
        "property",
        "property",
        "utility",
        "property",
        "go_to_jail",
        "property",
        "property",
        "community",
        "property",
        "station",
        "chance",
        "property",
        "tax",
        "property",
    )
    groups = (
        [1, 3],
        [6, 8, 9],
        [11, 13, 14],
        [16, 18, 19],
        [21, 23, 24],
        [26, 27, 29],
        [31, 32, 34],
        [37, 39],
    )
    colors = (
        "#8B5A3C",
        "#82CDE6",
        "#D94D92",
        "#EF962B",
        "#DA453E",
        "#E9CC3E",
        "#3D9D68",
        "#315CA8",
    )
    for board in CATALOG.boards:
        assert tuple(t.kind for t in board.tiles) == expected
        for indices, color in zip(groups, colors, strict=True):
            assert {board.tiles[i].color for i in indices} == {color}
            group = board.tiles[indices[0]].group
            assert [i for i, t in enumerate(board.tiles) if t.group == group] == indices
