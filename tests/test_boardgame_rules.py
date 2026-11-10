from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from random import Random

import pytest
from app.domain.boardgame.game import (
    Action,
    Command,
    Debt,
    Lot,
    Outcome,
    Phase,
    Player,
    Room,
    Seat,
    apply_command,
    auto_turn,
    board_for,
    net_worth,
    rent_for,
)
from app.domain.boardgame.validation import validate_catalog
from app.infrastructure.content.boardgame import load_board_catalog

CATALOG = load_board_catalog(Path("web/public/boardgame/catalog.json"))


def lobby(scenario: str = "almaty_first") -> Room:
    return Room(0, "human", scenario, (Seat("human", "Аян", "#479e8b", ready=True),))


def started(scenario: str = "almaty_first") -> Room:
    room = lobby(scenario)
    room = apply_command(
        CATALOG, room, "human", Command(0, Action.ADD_BOT, "balanced"), lambda n: 0
    ).room
    return apply_command(CATALOG, room, "human", Command(1, Action.START), lambda n: 0).room


def with_match(**changes: object) -> Room:
    room = started()
    assert room.match
    return replace(room, match=replace(room.match, **changes))


def test_only_host_can_start_and_people_must_be_ready() -> None:
    room = replace(lobby(), seats=(*lobby().seats, Seat("other", "Болат", "#d6a854")))
    assert (
        apply_command(CATALOG, room, "other", Command(0, Action.START), lambda n: 0).outcome
        == Outcome.FORBIDDEN
    )
    assert (
        apply_command(CATALOG, room, "human", Command(0, Action.START), lambda n: 0).outcome
        == Outcome.NOT_READY
    )
    ready = apply_command(CATALOG, room, "other", Command(0, Action.READY), lambda n: 0).room
    assert apply_command(CATALOG, ready, "human", Command(1, Action.START), lambda n: 0).room.match
    assert (
        apply_command(CATALOG, ready, "human", Command(0, Action.START), lambda n: 0).outcome
        == Outcome.STALE
    )
    full = started()
    assert (
        apply_command(
            CATALOG, full, "intruder", Command(full.revision, Action.ROLL), lambda n: 0
        ).outcome
        == Outcome.FORBIDDEN
    )


def test_dice_purchase_and_retry_do_not_move_or_spend_twice() -> None:
    room = started()
    rolled = apply_command(CATALOG, room, "human", Command(room.revision, Action.ROLL), lambda n: 0)
    assert rolled.outcome == Outcome.APPLIED and rolled.room.match
    assert rolled.room.match.dice == (1, 1) and rolled.room.match.pending == 2
    assert room.match and room.match.players[0].position == 0
    buy = apply_command(
        CATALOG, rolled.room, "human", Command(rolled.room.revision, Action.BUY), lambda n: 0
    )
    assert buy.room.match and buy.room.match.players[0].cash == 1100
    assert buy.room.match.lots["2"].owner == 0
    retry = apply_command(
        CATALOG, buy.room, "human", Command(rolled.room.revision, Action.BUY), lambda n: 0
    )
    assert retry.outcome == Outcome.STALE and retry.room is buy.room


def test_rent_is_transferred_to_owner_and_mortgage_suspends_rent() -> None:
    room = with_match(
        lots={"2": Lot(1)},
        players=(
            Player("human", "Аян", "#479e8b", "", 1200),
            Player("bot:0", "Айша", "#d6a854", "balanced", 1200),
        ),
    )
    result = apply_command(CATALOG, room, "human", Command(room.revision, Action.ROLL), lambda n: 0)
    assert result.room.match and [p.cash for p in result.room.match.players] == [1190, 1210]
    assert result.room.match.phase == Phase.END
    assert (
        room.match
        and rent_for(
            board_for(CATALOG, room), replace(room.match, lots={"2": Lot(1, mortgaged=True)}), 2
        )
        == 0
    )


def test_color_groups_even_building_and_liquidation_keep_capital_consistent() -> None:
    room = with_match(lots={"1": Lot(0), "2": Lot(0)})
    board = board_for(CATALOG, room)
    assert room.match and rent_for(board, room.match, 1) == 20
    build = apply_command(
        CATALOG, room, "human", Command(room.revision, Action.BUILD, tile=1), lambda n: 0
    )
    assert build.room.match and build.room.match.lots["1"].level == 1
    assert net_worth(board, build.room.match, 0) == net_worth(board, room.match, 0)
    assert (
        apply_command(
            CATALOG,
            build.room,
            "human",
            Command(build.room.revision, Action.BUILD, tile=1),
            lambda n: 0,
        ).outcome
        == Outcome.EVEN_BUILDING
    )
    assert (
        apply_command(
            CATALOG,
            build.room,
            "human",
            Command(build.room.revision, Action.MORTGAGE, tile=2),
            lambda n: 0,
        ).outcome
        == Outcome.SELL_FIRST
    )
    sold = apply_command(
        CATALOG, build.room, "human", Command(build.room.revision, Action.SELL, tile=1), lambda n: 0
    ).room
    mortgaged = apply_command(
        CATALOG, sold, "human", Command(sold.revision, Action.MORTGAGE, tile=1), lambda n: 0
    ).room
    assert mortgaged.match and sold.match
    assert net_worth(board, mortgaged.match, 0) == net_worth(board, sold.match, 0)
    redeemed = apply_command(
        CATALOG, mortgaged, "human", Command(mortgaged.revision, Action.REDEEM, tile=1), lambda n: 0
    ).room
    assert (
        redeemed.match
        and net_worth(board, redeemed.match, 0) == net_worth(board, mortgaged.match, 0) - 5
    )


def test_debt_requires_payment_or_bankruptcy_and_never_creates_negative_cash() -> None:
    room = with_match(
        lots={"2": Lot(1, 4)},
        players=(
            Player("human", "Аян", "#479e8b", "", 5),
            Player("bot:0", "Айша", "#d6a854", "balanced", 1200),
        ),
    )
    result = apply_command(
        CATALOG, room, "human", Command(room.revision, Action.ROLL), lambda n: 0
    ).room
    assert result.match and result.match.phase == Phase.DEBT and result.match.debt == Debt(300, 1)
    assert (
        apply_command(
            CATALOG, result, "human", Command(result.revision, Action.SETTLE), lambda n: 0
        ).outcome
        == Outcome.INSUFFICIENT
    )
    bankrupt = apply_command(
        CATALOG, result, "human", Command(result.revision, Action.BANKRUPT), lambda n: 0
    ).room
    assert bankrupt.match and bankrupt.match.phase == Phase.FINISHED and bankrupt.match.winner == 1
    assert [p.cash for p in bankrupt.match.players] == [0, 1205]


def test_human_trade_needs_seller_consent_and_cannot_be_accepted_twice() -> None:
    room = with_match(
        lots={"2": Lot(1)},
        players=(
            Player("human", "Аян", "#479e8b", "", 1200),
            Player("second", "Болат", "#d6a854", "", 1200),
        ),
    )
    room = replace(room, seats=(room.seats[0], Seat("second", "Болат", "#d6a854", ready=True)))
    offered = apply_command(
        CATALOG,
        room,
        "human",
        Command(room.revision, Action.OFFER, tile=2, amount=150),
        lambda n: 0,
    ).room
    assert offered.match and offered.match.lots["2"].owner == 1 and offered.match.offers
    offer = offered.match.offers[0]
    assert (
        apply_command(
            CATALOG,
            offered,
            "human",
            Command(offered.revision, Action.ACCEPT, offer.id),
            lambda n: 0,
        ).outcome
        == Outcome.FORBIDDEN
    )
    accepted = apply_command(
        CATALOG, offered, "second", Command(offered.revision, Action.ACCEPT, offer.id), lambda n: 0
    ).room
    assert accepted.match and accepted.match.lots["2"].owner == 0
    assert [p.cash for p in accepted.match.players] == [1050, 1350]
    assert (
        apply_command(
            CATALOG,
            accepted,
            "second",
            Command(offered.revision, Action.ACCEPT, offer.id),
            lambda n: 0,
        ).outcome
        == Outcome.STALE
    )


@pytest.mark.parametrize("scenario", [s.id for s in CATALOG.scenarios])
def test_every_scenario_finishes_with_bots_and_valid_economy(scenario: str) -> None:
    room = started(scenario)
    random = Random(42)
    for _ in range(300):
        assert room.match
        if room.match.phase == Phase.FINISHED:
            break
        room = auto_turn(CATALOG, room, random.randrange)
        assert room.match and all(p.cash >= 0 for p in room.match.players)
        assert all(
            0 <= lot.level <= 4 and 0 <= lot.owner < len(room.match.players)
            for lot in room.match.lots.values()
        )
    assert room.match and room.match.phase == Phase.FINISHED and room.match.winner >= 0


def test_content_constructor_rejects_invalid_rents_and_recursive_cards() -> None:
    board = CATALOG.boards[0]
    tile = replace(board.tiles[1], rents=())
    broken = replace(
        CATALOG,
        boards=(
            replace(board, tiles=(board.tiles[0], tile, *board.tiles[2:])),
            *CATALOG.boards[1:],
        ),
    )
    with pytest.raises(ValueError):
        validate_catalog(broken)
    with pytest.raises(ValueError):
        validate_catalog(
            replace(CATALOG, cards=(replace(CATALOG.cards[0], move=3), *CATALOG.cards[1:]))
        )
