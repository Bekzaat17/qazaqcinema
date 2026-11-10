from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import TypedDict, Unpack

RandomBelow = Callable[[int], int]


@dataclass(frozen=True, slots=True)
class Tile:
    id: str
    name: str
    kind: str
    group: str
    color: str
    price: int
    rents: tuple[int, ...]
    build_cost: int
    amount: int


@dataclass(frozen=True, slots=True)
class Board:
    id: str
    name: str
    subtitle: str
    biome: str
    ground: str
    sky: str
    accent: str
    tiles: tuple[Tile, ...]
    illustration: str = ""
    thumbnail: str = ""


@dataclass(frozen=True, slots=True)
class Scenario:
    id: str
    board: str
    name: str
    story: str
    round_limit: int
    starting_cash: int
    salary: int
    tax_multiplier: int
    event_multiplier: int
    reward: int


@dataclass(frozen=True, slots=True)
class Card:
    id: str
    text: str
    amount: int
    move: int | None
    skip: int


@dataclass(frozen=True, slots=True)
class Bot:
    id: str
    name: str
    reserve: int
    color: str


@dataclass(frozen=True, slots=True)
class Catalog:
    version: int
    boards: tuple[Board, ...]
    scenarios: tuple[Scenario, ...]
    cards: tuple[Card, ...]
    bots: tuple[Bot, ...]


class Phase(StrEnum):
    ROLL = "roll"
    BUY = "buy"
    END = "end"
    DEBT = "debt"
    FINISHED = "finished"


class Action(StrEnum):
    START = "start"
    CONFIGURE = "configure"
    ADD_BOT = "add_bot"
    REMOVE_BOT = "remove_bot"
    READY = "ready"
    ROLL = "roll"
    BUY = "buy"
    PASS = "pass"
    END = "end"
    BUILD = "build"
    SELL = "sell"
    MORTGAGE = "mortgage"
    REDEEM = "redeem"
    SETTLE = "settle"
    BANKRUPT = "bankrupt"
    OFFER = "offer"
    ACCEPT = "accept"
    REJECT = "reject"
    TIMEOUT = "timeout"


class Outcome(StrEnum):
    APPLIED = "applied"
    STALE = "stale"
    FORBIDDEN = "forbidden"
    INVALID = "invalid"
    INSUFFICIENT = "insufficient"
    GROUP_REQUIRED = "group_required"
    EVEN_BUILDING = "even_building"
    SELL_FIRST = "sell_first"
    NOT_READY = "not_ready"
    FULL = "full"
    BOT_DECLINED = "bot_declined"
    TOO_EARLY = "too_early"


@dataclass(frozen=True, slots=True)
class Seat:
    id: str
    name: str
    color: str
    bot: str = ""
    ready: bool = False


@dataclass(frozen=True, slots=True)
class Player:
    id: str
    name: str
    color: str
    bot: str
    cash: int
    position: int = 0
    bankrupt: bool = False
    skip: int = 0
    laps: int = 0


@dataclass(frozen=True, slots=True)
class Lot:
    owner: int
    level: int = 0
    mortgaged: bool = False


@dataclass(frozen=True, slots=True)
class Debt:
    amount: int
    creditor: int = -1


@dataclass(frozen=True, slots=True)
class Move:
    player: int
    start: int
    steps: int
    end: int
    dice: tuple[int, int]


@dataclass(frozen=True, slots=True)
class Offer:
    id: str
    buyer: int
    seller: int
    tile: int
    amount: int
    expires: int


@dataclass(frozen=True, slots=True)
class Match:
    catalog_version: int
    players: tuple[Player, ...]
    lots: dict[str, Lot] = field(default_factory=dict)
    turn: int = 0
    round: int = 1
    phase: Phase = Phase.ROLL
    dice: tuple[int, int] = (0, 0)
    pending: int = -1
    debt: Debt | None = None
    offers: tuple[Offer, ...] = ()
    log: tuple[str, ...] = ()
    moves: tuple[Move, ...] = ()
    winner: int = -1


@dataclass(frozen=True, slots=True)
class Room:
    revision: int
    host: str
    scenario_id: str
    seats: tuple[Seat, ...]
    match: Match | None = None
    closed: bool = False


@dataclass(frozen=True, slots=True)
class Command:
    revision: int
    kind: Action
    target: str = ""
    tile: int = -1
    amount: int = 0


@dataclass(frozen=True, slots=True)
class Result:
    room: Room
    outcome: Outcome


def board_for(catalog: Catalog, room: Room) -> Board:
    scenario = next(s for s in catalog.scenarios if s.id == room.scenario_id)
    return next(board for board in catalog.boards if board.id == scenario.board)


def net_worth(board: Board, match: Match, player: int) -> int:
    if match.players[player].bankrupt:
        return 0
    return match.players[player].cash + sum(
        board.tiles[int(key)].price
        + lot.level * board.tiles[int(key)].build_cost
        - (board.tiles[int(key)].price // 2 if lot.mortgaged else 0)
        for key, lot in match.lots.items()
        if lot.owner == player
    )


def group_indices(board: Board, tile: int) -> tuple[int, ...]:
    group = board.tiles[tile].group
    return tuple(i for i, item in enumerate(board.tiles) if group and item.group == group)


def rent_for(board: Board, match: Match, tile: int) -> int:
    lot = match.lots.get(str(tile))
    if not lot or lot.mortgaged:
        return 0
    spec = board.tiles[tile]
    if spec.kind == "station":
        count = sum(
            1
            for key, owned in match.lots.items()
            if owned.owner == lot.owner
            and not owned.mortgaged
            and board.tiles[int(key)].kind == "station"
        )
        return spec.rents[min(count - 1, len(spec.rents) - 1)]
    rent = spec.rents[lot.level]
    if lot.level == 0 and all(
        (owned := match.lots.get(str(index))) is not None
        and owned.owner == lot.owner
        and not owned.mortgaged
        for index in group_indices(board, tile)
    ):
        rent *= 2
    return rent


class PlayerChanges(TypedDict, total=False):
    cash: int
    position: int
    bankrupt: bool
    skip: int
    laps: int


def _player(match: Match, index: int, **changes: Unpack[PlayerChanges]) -> Match:
    players = list(match.players)
    players[index] = replace(players[index], **changes)
    return replace(match, players=tuple(players))


def _log(match: Match, text: str) -> Match:
    return replace(match, log=(*match.log, text)[-12:])


def _finish(board: Board, match: Match) -> Match:
    active = [i for i, player in enumerate(match.players) if not player.bankrupt]
    winner = max(active, key=lambda i: (net_worth(board, match, i), -i)) if active else -1
    return _log(
        replace(match, phase=Phase.FINISHED, winner=winner, offers=()),
        "Партия аяқталды! Капитал қорытындыланды.",
    )


def _charge(match: Match, amount: int, creditor: int = -1) -> Match:
    player = match.players[match.turn]
    if amount > player.cash:
        return _log(
            replace(match, phase=Phase.DEBT, debt=Debt(amount, creditor)),
            f"{player.name}: төлеуге {amount} ₸ керек.",
        )
    match = _player(match, match.turn, cash=player.cash - amount)
    if creditor >= 0:
        match = _player(match, creditor, cash=match.players[creditor].cash + amount)
    return replace(match, phase=Phase.END, debt=None)


def _land(
    catalog: Catalog, scenario: Scenario, board: Board, match: Match, random: RandomBelow
) -> Match:
    player = match.players[match.turn]
    index = player.position
    tile = board.tiles[index]
    match = _log(match, f"{player.name} → {tile.name}")
    if tile.kind in ("property", "station"):
        lot = match.lots.get(str(index))
        if lot is None:
            return replace(match, phase=Phase.BUY, pending=index)
        if lot.owner != match.turn and not lot.mortgaged:
            amount = rent_for(board, match, index)
            match = _log(match, f"Жалдау ақысы: {amount} ₸ → {match.players[lot.owner].name}")
            return _charge(match, amount, lot.owner)
    elif tile.kind == "tax":
        return _charge(
            _log(match, f"Алым: {tile.amount * scenario.tax_multiplier} ₸"),
            tile.amount * scenario.tax_multiplier,
        )
    elif tile.kind == "rest":
        match = _player(match, match.turn, cash=player.cash + tile.amount)
        match = _log(match, f"Наурыз сыйлығы: +{tile.amount} ₸")
    elif tile.kind == "chance":
        card = catalog.cards[random(len(catalog.cards))]
        match = _log(match, card.text)
        if card.move is not None:
            salary = scenario.salary if card.move < index else 0
            match = _player(
                match,
                match.turn,
                position=card.move,
                cash=player.cash + salary,
                laps=player.laps + int(salary > 0),
            )
            return _land(catalog, scenario, board, match, random)
        if card.skip:
            match = _player(match, match.turn, skip=player.skip + card.skip)
        amount = card.amount * scenario.event_multiplier
        if amount < 0:
            return _charge(match, -amount)
        if amount:
            match = _player(match, match.turn, cash=player.cash + amount)
            match = _log(match, f"+{amount} ₸")
    return replace(match, phase=Phase.END)


def _roll(
    catalog: Catalog, scenario: Scenario, board: Board, match: Match, random: RandomBelow
) -> Match:
    player = match.players[match.turn]
    if player.skip:
        return _log(
            replace(_player(match, match.turn, skip=player.skip - 1), phase=Phase.END),
            f"{player.name}: демалыс жүрісі.",
        )
    dice = (random(6) + 1, random(6) + 1)
    steps = sum(dice)
    end = (player.position + steps) % len(board.tiles)
    laps = (player.position + steps) // len(board.tiles)
    match = _player(
        match,
        match.turn,
        position=end,
        cash=player.cash + laps * scenario.salary,
        laps=player.laps + laps,
    )
    match = replace(
        match,
        dice=dice,
        moves=(*match.moves, Move(match.turn, player.position, steps, end, dice))[-8:],
    )
    if laps:
        match = _log(match, f"{player.name}: айналым табысы +{scenario.salary} ₸")
    return _land(catalog, scenario, board, match, random)


def _bankrupt(board: Board, match: Match) -> Match:
    debtor = match.turn
    creditor = match.debt.creditor if match.debt else -1
    if creditor >= 0:
        match = _player(
            match, creditor, cash=match.players[creditor].cash + match.players[debtor].cash
        )
    lots = {
        key: (replace(lot, owner=creditor) if lot.owner == debtor and creditor >= 0 else lot)
        for key, lot in match.lots.items()
        if lot.owner != debtor or creditor >= 0
    }
    match = _player(match, debtor, cash=0, bankrupt=True)
    match = _log(
        replace(
            match,
            lots=lots,
            debt=None,
            phase=Phase.END,
            offers=tuple(o for o in match.offers if o.buyer != debtor and o.seller != debtor),
        ),
        f"{match.players[debtor].name}: капитал таусылды.",
    )
    if sum(not p.bankrupt for p in match.players) <= 1:
        return _finish(board, match)
    return match


def _next(scenario: Scenario, board: Board, match: Match) -> Match:
    if sum(not p.bankrupt for p in match.players) <= 1:
        return _finish(board, match)
    index = match.turn
    round_number = match.round
    for _ in match.players:
        index = (index + 1) % len(match.players)
        if index == 0:
            round_number += 1
            if round_number > scenario.round_limit:
                return _finish(board, match)
        if not match.players[index].bankrupt:
            return replace(
                match,
                turn=index,
                round=round_number,
                phase=Phase.ROLL,
                pending=-1,
                debt=None,
                offers=tuple(o for o in match.offers if o.expires >= round_number),
            )
    return _finish(board, match)


def _manage(board: Board, match: Match, kind: Action, tile: int) -> tuple[Match, Outcome]:
    if not 0 <= tile < len(board.tiles):
        return match, Outcome.INVALID
    lot = match.lots.get(str(tile))
    if lot is None or lot.owner != match.turn:
        return match, Outcome.FORBIDDEN
    spec = board.tiles[tile]
    group = group_indices(board, tile)
    lots = dict(match.lots)
    cost = 0
    if kind == Action.BUILD:
        if match.phase == Phase.DEBT or spec.kind != "property" or lot.level >= len(spec.rents) - 1:
            return match, Outcome.INVALID
        if not all(
            (owned := lots.get(str(i))) is not None
            and owned.owner == lot.owner
            and not owned.mortgaged
            for i in group
        ):
            return match, Outcome.GROUP_REQUIRED
        if lot.level > min(lots[str(i)].level for i in group):
            return match, Outcome.EVEN_BUILDING
        cost = spec.build_cost
        lots[str(tile)] = replace(lot, level=lot.level + 1)
    elif kind == Action.SELL:
        if not lot.level:
            return match, Outcome.INVALID
        if lot.level < max(lots.get(str(i), Lot(-1)).level for i in group):
            return match, Outcome.EVEN_BUILDING
        cost = -(spec.build_cost // 2)
        lots[str(tile)] = replace(lot, level=lot.level - 1)
    elif kind == Action.MORTGAGE:
        if lot.mortgaged:
            return match, Outcome.INVALID
        if any(lots.get(str(i), Lot(-1)).level for i in group):
            return match, Outcome.SELL_FIRST
        cost = -(spec.price // 2)
        lots[str(tile)] = replace(lot, mortgaged=True)
    elif kind == Action.REDEEM:
        if not lot.mortgaged or match.phase == Phase.DEBT:
            return match, Outcome.INVALID
        cost = ((spec.price // 2) * 11 + 9) // 10
        lots[str(tile)] = replace(lot, mortgaged=False)
    else:
        return match, Outcome.INVALID
    player = match.players[match.turn]
    if player.cash < cost:
        return match, Outcome.INSUFFICIENT
    match = _player(replace(match, lots=lots), match.turn, cash=player.cash - cost)
    labels = {
        Action.BUILD: "Жақсартылды",
        Action.SELL: "Құрылыс сатылды",
        Action.MORTGAGE: "Кепілге қойылды",
        Action.REDEEM: "Кепілден қайтарылды",
    }
    return _log(match, f"{labels[kind]}: {spec.name}"), Outcome.APPLIED


def _trade(board: Board, room: Room, actor: int, command: Command) -> tuple[Match, Outcome]:
    assert room.match is not None
    match = room.match
    if match.phase in (Phase.DEBT, Phase.FINISHED) or match.players[actor].bankrupt:
        return match, Outcome.INVALID
    if command.kind == Action.OFFER:
        if not 0 <= command.tile < len(board.tiles) or command.amount < 1:
            return match, Outcome.INVALID
        lot = match.lots.get(str(command.tile))
        if not lot or lot.owner == actor or lot.level or lot.mortgaged:
            return match, Outcome.INVALID
        if any(match.lots.get(str(i), Lot(-1)).level for i in group_indices(board, command.tile)):
            return match, Outcome.SELL_FIRST
        if match.players[actor].cash < command.amount:
            return match, Outcome.INSUFFICIENT
        if match.players[lot.owner].bot:
            if command.amount < board.tiles[command.tile].price * 3 // 2:
                return match, Outcome.BOT_DECLINED
            match = _player(match, actor, cash=match.players[actor].cash - command.amount)
            match = _player(match, lot.owner, cash=match.players[lot.owner].cash + command.amount)
            lots = dict(match.lots)
            lots[str(command.tile)] = replace(lot, owner=actor)
            return _log(
                replace(match, lots=lots),
                f"Мәміле: {board.tiles[command.tile].name} — {command.amount} ₸",
            ), Outcome.APPLIED
        proposed = Offer(
            f"{room.revision}:{actor}",
            actor,
            lot.owner,
            command.tile,
            command.amount,
            match.round + 2,
        )
        return replace(
            match, offers=(*tuple(o for o in match.offers if o.buyer != actor), proposed)
        ), Outcome.APPLIED
    offer = next((o for o in match.offers if o.id == command.target), None)
    if not offer or offer.seller != actor:
        return match, Outcome.FORBIDDEN
    remaining = tuple(o for o in match.offers if o.id != offer.id)
    if command.kind == Action.REJECT:
        return replace(match, offers=remaining), Outcome.APPLIED
    lot = match.lots.get(str(offer.tile))
    if not lot or lot.owner != actor or lot.level or lot.mortgaged or offer.expires < match.round:
        return match, Outcome.INVALID
    if any(match.lots.get(str(i), Lot(-1)).level for i in group_indices(board, offer.tile)):
        return match, Outcome.SELL_FIRST
    if match.players[offer.buyer].bankrupt or match.players[offer.buyer].cash < offer.amount:
        return match, Outcome.INSUFFICIENT
    match = _player(match, actor, cash=match.players[actor].cash + offer.amount)
    match = _player(match, offer.buyer, cash=match.players[offer.buyer].cash - offer.amount)
    lots = dict(match.lots)
    lots[str(offer.tile)] = replace(lot, owner=offer.buyer)
    return _log(
        replace(match, lots=lots, offers=remaining),
        f"Мәміле: {board.tiles[offer.tile].name} — {offer.amount} ₸",
    ), Outcome.APPLIED


def _bot_turn(
    catalog: Catalog, scenario: Scenario, board: Board, match: Match, random: RandomBelow
) -> Match:
    profile = next(
        (bot for bot in catalog.bots if bot.id == match.players[match.turn].bot), catalog.bots[0]
    )
    if match.phase == Phase.ROLL:
        for index, tile in enumerate(board.tiles):
            if match.players[match.turn].cash >= tile.build_cost + profile.reserve:
                improved, outcome = _manage(board, match, Action.BUILD, index)
                if outcome == Outcome.APPLIED:
                    match = improved
                    break
        match = _roll(catalog, scenario, board, match, random)
    if match.phase == Phase.BUY:
        tile = board.tiles[match.pending]
        player = match.players[match.turn]
        if player.cash >= tile.price + profile.reserve // 2:
            lots = dict(match.lots)
            lots[str(match.pending)] = Lot(match.turn)
            match = _player(replace(match, lots=lots), match.turn, cash=player.cash - tile.price)
            match = _log(match, f"{player.name}: сатып алды — {tile.name}")
        match = replace(match, phase=Phase.END, pending=-1)
    if match.phase == Phase.DEBT:
        for kind in (Action.SELL, Action.MORTGAGE):
            for _ in range(len(board.tiles) * 4):
                if match.players[match.turn].cash >= match.debt.amount:  # type: ignore[union-attr]
                    break
                changed = False
                for index in range(len(board.tiles)):
                    updated, outcome = _manage(board, match, kind, index)
                    if outcome == Outcome.APPLIED:
                        match = updated
                        changed = True
                        break
                if not changed:
                    break
        debt = match.debt
        if debt and match.players[match.turn].cash >= debt.amount:
            match = _charge(match, debt.amount, debt.creditor)
        else:
            match = _bankrupt(board, match)
    if match.phase == Phase.END:
        match = _next(scenario, board, match)
    return match


def _bots(
    catalog: Catalog, scenario: Scenario, board: Board, match: Match, random: RandomBelow
) -> Match:
    for _ in range((scenario.round_limit + 1) * len(match.players)):
        if match.phase == Phase.FINISHED or not match.players[match.turn].bot:
            return match
        match = _bot_turn(catalog, scenario, board, match, random)
    return _finish(board, match)


def apply_command(
    catalog: Catalog, room: Room, actor: str, command: Command, random: RandomBelow
) -> Result:
    if room.revision != command.revision:
        return Result(room, Outcome.STALE)
    if room.closed or not any(seat.id == actor for seat in room.seats):
        return Result(room, Outcome.FORBIDDEN)
    if room.match is None:
        return _lobby(catalog, room, actor, command)
    match = deepcopy(room.match)
    if match.catalog_version != catalog.version or match.phase == Phase.FINISHED:
        return Result(room, Outcome.INVALID)
    index = next(i for i, player in enumerate(match.players) if player.id == actor)
    board = board_for(catalog, room)
    scenario = next(s for s in catalog.scenarios if s.id == room.scenario_id)
    if command.kind in (Action.OFFER, Action.ACCEPT, Action.REJECT):
        match, outcome = _trade(board, replace(room, match=match), index, command)
        if outcome != Outcome.APPLIED:
            return Result(room, outcome)
    else:
        if index != match.turn:
            return Result(room, Outcome.FORBIDDEN)
        if command.kind == Action.ROLL and match.phase == Phase.ROLL:
            match = _roll(catalog, scenario, board, match, random)
        elif command.kind in (Action.BUY, Action.PASS) and match.phase == Phase.BUY:
            if command.kind == Action.BUY:
                tile = board.tiles[match.pending]
                player = match.players[index]
                if player.cash < tile.price:
                    return Result(room, Outcome.INSUFFICIENT)
                lots = dict(match.lots)
                lots[str(match.pending)] = Lot(index)
                match = _player(replace(match, lots=lots), index, cash=player.cash - tile.price)
                match = _log(match, f"{player.name}: сатып алды — {tile.name}")
            match = replace(match, phase=Phase.END, pending=-1)
        elif command.kind == Action.END and match.phase == Phase.END:
            match = _next(scenario, board, match)
        elif command.kind in (Action.BUILD, Action.SELL, Action.MORTGAGE, Action.REDEEM):
            match, outcome = _manage(board, match, command.kind, command.tile)
            if outcome != Outcome.APPLIED:
                return Result(room, outcome)
        elif command.kind == Action.SETTLE and match.phase == Phase.DEBT and match.debt:
            if match.players[index].cash < match.debt.amount:
                return Result(room, Outcome.INSUFFICIENT)
            match = _charge(match, match.debt.amount, match.debt.creditor)
        elif command.kind == Action.BANKRUPT and match.phase == Phase.DEBT:
            match = _bankrupt(board, match)
            if match.phase != Phase.FINISHED:
                match = _next(scenario, board, match)
        else:
            return Result(room, Outcome.INVALID)
    match = _bots(catalog, scenario, board, match, random)
    return Result(replace(room, revision=room.revision + 1, match=match), Outcome.APPLIED)


def auto_turn(catalog: Catalog, room: Room, random: RandomBelow) -> Room:
    if not room.match or room.match.phase == Phase.FINISHED:
        return room
    scenario = next(s for s in catalog.scenarios if s.id == room.scenario_id)
    board = board_for(catalog, room)
    match = _bot_turn(catalog, scenario, board, deepcopy(room.match), random)
    match = _bots(catalog, scenario, board, match, random)
    return replace(room, revision=room.revision + 1, match=match)


def _lobby(catalog: Catalog, room: Room, actor: str, command: Command) -> Result:
    seats = room.seats
    if command.kind == Action.READY:
        seats = tuple(
            replace(seat, ready=not seat.ready) if seat.id == actor else seat for seat in seats
        )
        return Result(replace(room, revision=room.revision + 1, seats=seats), Outcome.APPLIED)
    if actor != room.host:
        return Result(room, Outcome.FORBIDDEN)
    if command.kind == Action.CONFIGURE:
        if not any(s.id == command.target for s in catalog.scenarios):
            return Result(room, Outcome.INVALID)
        seats = tuple(replace(seat, ready=bool(seat.bot) or seat.id == actor) for seat in seats)
        return Result(
            replace(room, revision=room.revision + 1, scenario_id=command.target, seats=seats),
            Outcome.APPLIED,
        )
    if command.kind == Action.ADD_BOT:
        if len(seats) >= 4:
            return Result(room, Outcome.FULL)
        bot = next((b for b in catalog.bots if b.id == command.target), None)
        if bot is None or any(seat.bot == command.target for seat in seats):
            return Result(room, Outcome.INVALID)
        seat = Seat(f"bot:{room.revision}", bot.name, bot.color, bot.id, True)
        return Result(
            replace(room, revision=room.revision + 1, seats=(*seats, seat)), Outcome.APPLIED
        )
    if command.kind == Action.REMOVE_BOT:
        if not any(seat.id == command.target and seat.bot for seat in seats):
            return Result(room, Outcome.INVALID)
        return Result(
            replace(
                room,
                revision=room.revision + 1,
                seats=tuple(s for s in seats if s.id != command.target),
            ),
            Outcome.APPLIED,
        )
    if command.kind == Action.START:
        if len(seats) < 2 or not all(seat.ready or seat.id == room.host for seat in seats):
            return Result(room, Outcome.NOT_READY)
        scenario = next(s for s in catalog.scenarios if s.id == room.scenario_id)
        seats = tuple(sorted(seats, key=lambda seat: seat.id != room.host))
        players = tuple(Player(s.id, s.name, s.color, s.bot, scenario.starting_cash) for s in seats)
        match = Match(catalog.version, players, log=("Сәтті партия! Алғашқы жүріс сенікі.",))
        return Result(replace(room, revision=room.revision + 1, match=match), Outcome.APPLIED)
    return Result(room, Outcome.INVALID)
