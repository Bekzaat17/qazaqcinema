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
    street: str = ""
    landmark: str = ""
    sprite: int = -1
    street_sprite: int = -1


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
    miniature_atlas: str = ""
    street_atlas: str = ""


@dataclass(frozen=True, slots=True)
class Scenario:
    id: str
    board: str
    name: str
    story: str
    round_limit: int  # 0 — до одного оставшегося участника.
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
    deck: str = "chance"


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
    legacy_catalogs: tuple[Catalog, ...] = ()


class Phase(StrEnum):
    ROLL = "roll"
    BUY = "buy"
    END = "end"
    DEBT = "debt"
    FINISHED = "finished"


class Action(StrEnum):
    BAIL = "bail"
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
    ASK = "ask"
    COUNTER = "counter"
    WITHDRAW = "withdraw"
    ACCEPT = "accept"
    REJECT = "reject"
    TIMEOUT = "timeout"


class Outcome(StrEnum):
    CHANNEL_REQUIRED = "channel_required"
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
    give_tile: int = -1
    proposer: int = -1


@dataclass(frozen=True, slots=True)
class ClassicState:
    jailed: dict[str, int] = field(default_factory=dict)
    doubles: int = 0
    release_steps: int = 0


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
    classic: ClassicState | None = None


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
    give_tile: int = -1


@dataclass(frozen=True, slots=True)
class Result:
    room: Room
    outcome: Outcome


def active_catalog(catalog: Catalog, room: Room) -> Catalog:
    if room.match and room.match.catalog_version == catalog.version:
        return catalog
    if not room.match and any(s.id == room.scenario_id for s in catalog.scenarios):
        return catalog
    for archived in catalog.legacy_catalogs:
        if (room.match and room.match.catalog_version == archived.version) or (
            not room.match and any(s.id == room.scenario_id for s in archived.scenarios)
        ):
            return archived
    return catalog


def board_for(catalog: Catalog, room: Room) -> Board:
    catalog = active_catalog(catalog, room)
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
    if spec.kind == "utility":
        count = sum(
            1
            for key, owned in match.lots.items()
            if owned.owner == lot.owner
            and not owned.mortgaged
            and board.tiles[int(key)].kind == "utility"
        )
        return sum(match.dice) * (10 if count >= 2 else 4)
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
    if tile.kind in ("property", "station", "utility"):
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
    elif tile.kind == "go_to_jail":
        return _to_jail(match)
    elif tile.kind in ("chance", "community"):
        cards = tuple(
            c
            for c in catalog.cards
            if c.deck == ("community" if tile.kind == "community" else "chance")
        )
        card = cards[random(len(cards))]
        match = _log(match, card.text)
        if card.id == "jail" and match.classic:
            return _to_jail(match)
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


def _to_jail(match: Match) -> Match:
    if not match.classic:
        return replace(match, phase=Phase.END)
    jailed = {**match.classic.jailed, str(match.turn): 0}
    match = _player(match, match.turn, position=10)
    return _log(
        replace(match, phase=Phase.END, pending=-1, classic=ClassicState(jailed)),
        "Түрмеге бар. Шығу: дубль немесе 50 ◈.",
    )


def _advance(
    catalog: Catalog,
    scenario: Scenario,
    board: Board,
    match: Match,
    steps: int,
    random: RandomBelow,
) -> Match:
    player = match.players[match.turn]
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
        match, moves=(*match.moves, Move(match.turn, player.position, steps, end, match.dice))[-8:]
    )
    if laps:
        match = _log(match, f"{player.name}: айналым табысы +{scenario.salary} ₸")
    return _land(catalog, scenario, board, match, random)


def _settle_payment(
    catalog: Catalog,
    scenario: Scenario,
    board: Board,
    match: Match,
    random: RandomBelow,
) -> Match:
    assert match.debt
    match = _charge(match, match.debt.amount, match.debt.creditor)
    if match.classic and match.classic.release_steps:
        steps = match.classic.release_steps
        match = replace(match, classic=replace(match.classic, release_steps=0))
        match = _advance(catalog, scenario, board, match, steps, random)
    return match


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
    match = replace(match, dice=dice)
    steps = sum(dice)
    classic = match.classic
    if classic:
        key = str(match.turn)
        if key in classic.jailed:
            attempts = classic.jailed[key] + 1
            if dice[0] != dice[1] and attempts < 3:
                return _log(
                    replace(
                        match,
                        phase=Phase.END,
                        classic=replace(
                            classic, jailed={**classic.jailed, key: attempts}, doubles=0
                        ),
                    ),
                    "Дубль түспеді. Келесі жүрісте қайта көр.",
                )
            jailed = {k: v for k, v in classic.jailed.items() if k != key}
            match = replace(match, classic=ClassicState(jailed))
            if dice[0] != dice[1]:
                if player.cash < 50:
                    return _charge(
                        replace(match, classic=ClassicState(jailed, release_steps=steps)), 50
                    )
                match = _player(match, match.turn, cash=player.cash - 50)
            return _advance(catalog, scenario, board, match, steps, random)
        doubles = classic.doubles + 1 if dice[0] == dice[1] else 0
        match = replace(match, classic=replace(classic, doubles=doubles))
        if doubles == 3:
            return _to_jail(match)
    return _advance(catalog, scenario, board, match, steps, random)


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
    if (
        match.classic
        and match.classic.doubles
        and str(match.turn) not in match.classic.jailed
        and not match.players[match.turn].bankrupt
    ):
        return _log(
            replace(match, phase=Phase.ROLL, pending=-1, debt=None), "Дубль! Тағы бір рет лақтыр."
        )
    if match.classic:
        match = replace(match, classic=replace(match.classic, doubles=0, release_steps=0))
    if sum(not p.bankrupt for p in match.players) <= 1:
        return _finish(board, match)
    index = match.turn
    round_number = match.round
    for _ in match.players:
        index = (index + 1) % len(match.players)
        if index == 0:
            round_number += 1
            if scenario.round_limit and round_number > scenario.round_limit:
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


def _tradeable(board: Board, match: Match, tile: int, owner: int) -> Outcome:
    if not 0 <= tile < len(board.tiles):
        return Outcome.INVALID
    lot = match.lots.get(str(tile))
    if not lot or lot.owner != owner or lot.level or lot.mortgaged:
        return Outcome.INVALID
    if any(match.lots.get(str(i), Lot(-1)).level for i in group_indices(board, tile)):
        return Outcome.SELL_FIRST
    return Outcome.APPLIED


def _transfer_trade(
    board: Board,
    match: Match,
    buyer: int,
    seller: int,
    tile: int,
    amount: int,
    give_tile: int,
) -> Match:
    match = _player(match, buyer, cash=match.players[buyer].cash - amount)
    match = _player(match, seller, cash=match.players[seller].cash + amount)
    lots = dict(match.lots)
    lots[str(tile)] = replace(lots[str(tile)], owner=buyer)
    if give_tile >= 0:
        lots[str(give_tile)] = replace(lots[str(give_tile)], owner=seller)
        label = f"Айырбас: {board.tiles[tile].name} ↔ {board.tiles[give_tile].name} · {amount} ◈"
    else:
        label = f"Мәміле: {board.tiles[tile].name} — {amount} ₸"
    return _log(replace(match, lots=lots), label)


def _offer_sender(offer: Offer) -> int:
    return offer.proposer if offer.proposer >= 0 else offer.buyer


def _offer_recipient(offer: Offer) -> int:
    return offer.seller if _offer_sender(offer) == offer.buyer else offer.buyer


def _trade(board: Board, room: Room, actor: int, command: Command) -> tuple[Match, Outcome]:
    assert room.match is not None
    match = room.match
    if match.phase in (Phase.DEBT, Phase.FINISHED) or match.players[actor].bankrupt:
        return match, Outcome.INVALID
    if command.kind in (Action.OFFER, Action.ASK, Action.COUNTER):
        previous = None
        if command.kind == Action.COUNTER:
            previous = next((o for o in match.offers if o.id == command.target), None)
            if not previous or _offer_recipient(previous) != actor:
                return match, Outcome.FORBIDDEN
            if previous.expires < match.round:
                return match, Outcome.INVALID
            buyer, seller, tile = previous.buyer, previous.seller, previous.tile
        elif command.kind == Action.ASK:
            buyer = next((i for i, p in enumerate(match.players) if p.id == command.target), -1)
            seller, tile = actor, command.tile
            if buyer < 0 or buyer == actor:
                return match, Outcome.INVALID
        else:
            buyer, tile = actor, command.tile
            lot = match.lots.get(str(tile))
            if not lot or lot.owner == actor:
                return match, Outcome.INVALID
            seller = lot.owner
        if (
            command.give_tile < -1
            or command.amount < 0
            or (command.give_tile == -1 and command.amount < 1)
            or match.players[buyer].bankrupt
            or match.players[seller].bankrupt
        ):
            return match, Outcome.INVALID
        outcome = _tradeable(board, match, tile, seller)
        if outcome != Outcome.APPLIED:
            return match, outcome
        if command.give_tile >= 0:
            outcome = _tradeable(board, match, command.give_tile, buyer)
            if outcome != Outcome.APPLIED:
                return match, outcome
        if match.players[buyer].cash < command.amount:
            return match, Outcome.INSUFFICIENT
        recipient = seller if actor == buyer else buyer
        if match.players[recipient].bot:
            cost = command.amount + (
                board.tiles[command.give_tile].price if command.give_tile >= 0 else 0
            )
            accepted = (
                cost >= board.tiles[tile].price * 3 // 2
                if recipient == seller
                else cost <= board.tiles[tile].price * 2 // 3
            )
            if not accepted:
                return match, Outcome.BOT_DECLINED
            return _transfer_trade(
                board, match, buyer, seller, tile, command.amount, command.give_tile
            ), Outcome.APPLIED
        proposed = Offer(
            f"{room.revision}:{actor}",
            buyer,
            seller,
            tile,
            command.amount,
            match.round + 2,
            command.give_tile,
            actor,
        )
        remaining = tuple(
            o
            for o in match.offers
            if _offer_sender(o) != actor and (previous is None or o.id != previous.id)
        )
        return replace(match, offers=(*remaining, proposed)), Outcome.APPLIED
    offer = next((o for o in match.offers if o.id == command.target), None)
    if not offer:
        return match, Outcome.FORBIDDEN
    remaining = tuple(o for o in match.offers if o.id != offer.id)
    if command.kind == Action.WITHDRAW:
        if _offer_sender(offer) != actor:
            return match, Outcome.FORBIDDEN
        return replace(match, offers=remaining), Outcome.APPLIED
    if _offer_recipient(offer) != actor:
        return match, Outcome.FORBIDDEN
    if command.kind == Action.REJECT:
        return replace(match, offers=remaining), Outcome.APPLIED
    if offer.expires < match.round or match.players[offer.seller].bankrupt:
        return match, Outcome.INVALID
    outcome = _tradeable(board, match, offer.tile, offer.seller)
    if outcome != Outcome.APPLIED:
        return match, outcome
    if offer.give_tile >= 0:
        outcome = _tradeable(board, match, offer.give_tile, offer.buyer)
        if outcome != Outcome.APPLIED:
            return match, outcome
    if match.players[offer.buyer].bankrupt or match.players[offer.buyer].cash < offer.amount:
        return match, Outcome.INSUFFICIENT
    match = _transfer_trade(
        board, match, offer.buyer, offer.seller, offer.tile, offer.amount, offer.give_tile
    )
    return replace(match, offers=remaining), Outcome.APPLIED


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
            match = _settle_payment(catalog, scenario, board, match, random)
            if match.phase in (Phase.BUY, Phase.DEBT):
                return _bot_turn(catalog, scenario, board, match, random)
        else:
            match = _bankrupt(board, match)
    if match.phase == Phase.END:
        match = _next(scenario, board, match)
    return match


def _bots(
    catalog: Catalog, scenario: Scenario, board: Board, match: Match, random: RandomBelow
) -> Match:
    # Без лимита кругов обрабатываем ботов порциями, не назначая победителя по таймауту.
    limit = (scenario.round_limit + 1) * len(match.players) if scenario.round_limit else 128
    for _ in range(limit):
        if match.phase == Phase.FINISHED or not match.players[match.turn].bot:
            return match
        match = _bot_turn(catalog, scenario, board, match, random)
    return _finish(board, match) if scenario.round_limit else match


def apply_command(
    catalog: Catalog, room: Room, actor: str, command: Command, random: RandomBelow
) -> Result:
    catalog = active_catalog(catalog, room)
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
    if command.kind in (
        Action.OFFER,
        Action.ASK,
        Action.COUNTER,
        Action.WITHDRAW,
        Action.ACCEPT,
        Action.REJECT,
    ):
        match, outcome = _trade(board, replace(room, match=match), index, command)
        if outcome != Outcome.APPLIED:
            return Result(room, outcome)
    else:
        if index != match.turn:
            return Result(room, Outcome.FORBIDDEN)
        if command.kind == Action.ROLL and match.phase == Phase.ROLL:
            match = _roll(catalog, scenario, board, match, random)
        elif command.kind == Action.BAIL and match.phase == Phase.ROLL:
            if not match.classic or str(index) not in match.classic.jailed:
                return Result(room, Outcome.INVALID)
            if match.players[index].cash < 50:
                return Result(room, Outcome.INSUFFICIENT)
            jailed = {k: v for k, v in match.classic.jailed.items() if k != str(index)}
            match = _player(
                replace(match, classic=ClassicState(jailed)),
                index,
                cash=match.players[index].cash - 50,
            )
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
            match = _settle_payment(catalog, scenario, board, match, random)
        elif command.kind == Action.BANKRUPT and match.phase == Phase.DEBT:
            match = _bankrupt(board, match)
            if match.phase != Phase.FINISHED:
                match = _next(scenario, board, match)
        else:
            return Result(room, Outcome.INVALID)
    match = _bots(catalog, scenario, board, match, random)
    return Result(replace(room, revision=room.revision + 1, match=match), Outcome.APPLIED)


def auto_turn(catalog: Catalog, room: Room, random: RandomBelow) -> Room:
    catalog = active_catalog(catalog, room)
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
        board = next(b for b in catalog.boards if b.id == scenario.board)
        match = Match(
            catalog.version,
            players,
            log=("Сәтті партия! Алғашқы жүріс сенікі.",),
            classic=ClassicState() if len(board.tiles) == 40 else None,
        )
        return Result(replace(room, revision=room.revision + 1, match=match), Outcome.APPLIED)
    return Result(room, Outcome.INVALID)
