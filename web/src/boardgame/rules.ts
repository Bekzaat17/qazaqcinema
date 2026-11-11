import type {
  Action,
  Board,
  Catalog,
  Command,
  Match,
  Offer,
  Outcome,
  RandomBelow,
  Result,
  Room,
  Scenario,
} from "./types.ts";

export function activeCatalog(catalog: Catalog, room: Room): Catalog {
  if (room.match?.catalog_version === catalog.version || (!room.match && catalog.scenarios.some((s) => s.id === room.scenario_id))) return catalog;
  return catalog.legacy_catalogs?.find((past) => room.match ? past.version === room.match.catalog_version
    : past.scenarios.some((s) => s.id === room.scenario_id)) ?? catalog;
}
export const boardFor = (catalog: Catalog, room: Room): Board => {
  const definitions = activeCatalog(catalog, room);
  return definitions.boards.find((b) => b.id === definitions.scenarios.find((s) => s.id === room.scenario_id)!.board)!;
};
export const groupIndices = (board: Board, tile: number): number[] =>
  board.tiles.flatMap((t, i) =>
    board.tiles[tile].group && t.group === board.tiles[tile].group ? [i] : [],
  );
export function netWorth(board: Board, match: Match, player: number): number {
  return match.players[player].bankrupt
    ? 0
    : match.players[player].cash +
        Object.entries(match.lots).reduce(
          (sum, [key, lot]) =>
            sum +
            (lot.owner === player
              ? board.tiles[+key].price +
                lot.level * board.tiles[+key].build_cost -
                (lot.mortgaged ? Math.floor(board.tiles[+key].price / 2) : 0)
              : 0),
          0,
        );
}
export function rentFor(board: Board, match: Match, tile: number): number {
  const lot = match.lots[tile];
  if (!lot || lot.mortgaged) return 0;
  const spec = board.tiles[tile];
  if (spec.kind === "station") {
    const count = Object.entries(match.lots).filter(
      ([key, l]) =>
        l.owner === lot.owner &&
        !l.mortgaged &&
        board.tiles[+key].kind === "station",
    ).length;
    return spec.rents[Math.min(count - 1, spec.rents.length - 1)];
  }
  if (spec.kind === "utility") {
    const count = Object.entries(match.lots).filter(([key, owned]) => owned.owner === lot.owner && !owned.mortgaged && board.tiles[+key].kind === "utility").length;
    return (match.dice[0] + match.dice[1]) * (count >= 2 ? 10 : 4);
  }
  let rent = spec.rents[lot.level];
  if (
    !lot.level &&
    groupIndices(board, tile).every(
      (i) => match.lots[i]?.owner === lot.owner && !match.lots[i].mortgaged,
    )
  )
    rent *= 2;
  return rent;
}
function log(match: Match, text: string) {
  match.log.push(text);
  match.log = match.log.slice(-12);
}
function finish(board: Board, match: Match) {
  const active = match.players
    .map((p, i) => (p.bankrupt ? -1 : i))
    .filter((i) => i >= 0);
  active.sort(
    (a, b) => netWorth(board, match, b) - netWorth(board, match, a) || a - b,
  );
  match.winner = active[0] ?? -1;
  match.phase = "finished";
  match.offers = [];
  log(match, "Партия аяқталды! Капитал қорытындыланды.");
}
function charge(match: Match, amount: number, creditor = -1) {
  const player = match.players[match.turn];
  if (amount > player.cash) {
    match.phase = "debt";
    match.debt = { amount, creditor };
    log(match, `${player.name}: төлеуге ${amount} ₸ керек.`);
    return;
  }
  player.cash -= amount;
  if (creditor >= 0) match.players[creditor].cash += amount;
  match.phase = "end";
  match.debt = null;
}
function land(
  catalog: Catalog,
  scenario: Scenario,
  board: Board,
  match: Match,
  random: RandomBelow,
) {
  const player = match.players[match.turn],
    index = player.position,
    tile = board.tiles[index];
  log(match, `${player.name} → ${tile.name}`);
  if (["property", "station", "utility"].includes(tile.kind)) {
    const lot = match.lots[index];
    if (!lot) {
      match.phase = "buy";
      match.pending = index;
      return;
    }
    if (lot.owner !== match.turn && !lot.mortgaged) {
      const amount = rentFor(board, match, index);
      log(
        match,
        `Жалдау ақысы: ${amount} ₸ → ${match.players[lot.owner].name}`,
      );
      charge(match, amount, lot.owner);
      return;
    }
  } else if (tile.kind === "tax") {
    log(match, `Алым: ${tile.amount * scenario.tax_multiplier} ₸`);
    charge(match, tile.amount * scenario.tax_multiplier);
    return;
  } else if (tile.kind === "rest") {
    player.cash += tile.amount;
    log(match, `Наурыз сыйлығы: +${tile.amount} ₸`);
  } else if (tile.kind === "go_to_jail") {
    toJail(match); return;
  } else if (["chance", "community"].includes(tile.kind)) {
    const cards = catalog.cards.filter((card) => (card.deck ?? "chance") === (tile.kind === "community" ? "community" : "chance"));
    const card = cards[random(cards.length)];
    log(match, card.text);
    if (card.id === "jail" && match.classic) { toJail(match); return; }
    if (card.move !== null) {
      const salary = card.move < index ? scenario.salary : 0;
      player.position = card.move;
      player.cash += salary;
      player.laps += Number(salary > 0);
      land(catalog, scenario, board, match, random);
      return;
    }
    if (card.skip) player.skip += card.skip;
    const amount = card.amount * scenario.event_multiplier;
    if (amount < 0) {
      charge(match, -amount);
      return;
    }
    if (amount) {
      player.cash += amount;
      log(match, `+${amount} ₸`);
    }
  }
  match.phase = "end";
}
function toJail(match: Match) {
  if (match.classic) {
    match.players[match.turn].position = 10;
    match.classic.jailed[match.turn] = 0;
    match.classic.doubles = 0;
    match.classic.release_steps = 0;
    log(match, "Түрмеге бар. Шығу: дубль немесе 50 ◈.");
  }
  match.phase = "end"; match.pending = -1;
}
function advance(catalog: Catalog, scenario: Scenario, board: Board, match: Match,
  steps: number, random: RandomBelow) {
  const player = match.players[match.turn], start = player.position;
  const end = (start + steps) % board.tiles.length, laps = Math.floor((start + steps) / board.tiles.length);
  player.position = end; player.cash += laps * scenario.salary; player.laps += laps;
  match.moves.push({ player: match.turn, start, steps, end, dice: match.dice });
  match.moves = match.moves.slice(-8);
  if (laps) log(match, `${player.name}: айналым табысы +${scenario.salary} ₸`);
  land(catalog, scenario, board, match, random);
}
function settlePayment(catalog: Catalog, scenario: Scenario, board: Board, match: Match, random: RandomBelow) {
  const debt = match.debt!;
  charge(match, debt.amount, debt.creditor);
  if (match.classic?.release_steps) {
    const steps = match.classic.release_steps; match.classic.release_steps = 0;
    advance(catalog, scenario, board, match, steps, random);
  }
}
function roll(catalog: Catalog, scenario: Scenario, board: Board, match: Match, random: RandomBelow) {
  const player = match.players[match.turn];
  if (player.skip) { player.skip--; match.phase = "end"; log(match, `${player.name}: демалыс жүрісі.`); return; }
  match.dice = [random(6) + 1, random(6) + 1];
  const steps = match.dice[0] + match.dice[1], classic = match.classic;
  if (classic) {
    const key = String(match.turn);
    if (key in classic.jailed) {
      const attempts = classic.jailed[key] + 1;
      if (match.dice[0] !== match.dice[1] && attempts < 3) {
        classic.jailed[key] = attempts; classic.doubles = 0; match.phase = "end";
        log(match, "Дубль түспеді. Келесі жүрісте қайта көр."); return;
      }
      delete classic.jailed[key]; classic.doubles = 0; classic.release_steps = 0;
      if (match.dice[0] !== match.dice[1]) {
        if (player.cash < 50) { classic.release_steps = steps; charge(match, 50); return; }
        player.cash -= 50;
      }
      advance(catalog, scenario, board, match, steps, random); return;
    }
    classic.doubles = match.dice[0] === match.dice[1] ? classic.doubles + 1 : 0;
    if (classic.doubles === 3) { toJail(match); return; }
  }
  advance(catalog, scenario, board, match, steps, random);
}
function bankrupt(board: Board, match: Match) {
  const debtor = match.turn,
    creditor = match.debt?.creditor ?? -1;
  if (creditor >= 0) match.players[creditor].cash += match.players[debtor].cash;
  for (const [key, lot] of Object.entries(match.lots))
    if (lot.owner === debtor) {
      if (creditor >= 0) lot.owner = creditor;
      else delete match.lots[key];
    }
  match.players[debtor].cash = 0;
  match.players[debtor].bankrupt = true;
  match.debt = null;
  match.phase = "end";
  match.offers = match.offers.filter(
    (o) => o.buyer !== debtor && o.seller !== debtor,
  );
  log(match, `${match.players[debtor].name}: капитал таусылды.`);
  if (match.players.filter((p) => !p.bankrupt).length <= 1)
    finish(board, match);
}
function next(scenario: Scenario, board: Board, match: Match) {
  if (match.classic?.doubles && !(String(match.turn) in match.classic.jailed) && !match.players[match.turn].bankrupt) {
    match.phase = "roll"; match.pending = -1; match.debt = null;
    log(match, "Дубль! Тағы бір рет лақтыр."); return;
  }
  if (match.classic) { match.classic.doubles = 0; match.classic.release_steps = 0; }
  if (match.players.filter((p) => !p.bankrupt).length <= 1) {
    finish(board, match);
    return;
  }
  let index = match.turn,
    round = match.round;
  for (let i = 0; i < match.players.length; i++) {
    index = (index + 1) % match.players.length;
    if (index === 0) {
      round++;
      if (scenario.round_limit > 0 && round > scenario.round_limit) {
        finish(board, match);
        return;
      }
    }
    if (!match.players[index].bankrupt) {
      match.turn = index;
      match.round = round;
      match.phase = "roll";
      match.pending = -1;
      match.debt = null;
      match.offers = match.offers.filter((o) => o.expires >= round);
      return;
    }
  }
  finish(board, match);
}
function manage(
  board: Board,
  match: Match,
  kind: Action,
  tile: number,
): Outcome {
  if (tile < 0 || tile >= board.tiles.length) return "invalid";
  const lot = match.lots[tile];
  if (!lot || lot.owner !== match.turn) return "forbidden";
  const spec = board.tiles[tile],
    group = groupIndices(board, tile);
  let cost = 0;
  const changed = { ...lot };
  if (kind === "build") {
    if (
      match.phase === "debt" ||
      spec.kind !== "property" ||
      lot.level >= spec.rents.length - 1
    )
      return "invalid";
    if (
      !group.every(
        (i) => match.lots[i]?.owner === lot.owner && !match.lots[i].mortgaged,
      )
    )
      return "group_required";
    if (lot.level > Math.min(...group.map((i) => match.lots[i].level)))
      return "even_building";
    cost = spec.build_cost;
    changed.level++;
  } else if (kind === "sell") {
    if (!lot.level) return "invalid";
    if (lot.level < Math.max(...group.map((i) => match.lots[i]?.level ?? 0)))
      return "even_building";
    cost = -Math.floor(spec.build_cost / 2);
    changed.level--;
  } else if (kind === "mortgage") {
    if (lot.mortgaged) return "invalid";
    if (group.some((i) => (match.lots[i]?.level ?? 0) > 0)) return "sell_first";
    cost = -Math.floor(spec.price / 2);
    changed.mortgaged = true;
  } else if (kind === "redeem") {
    if (!lot.mortgaged || match.phase === "debt") return "invalid";
    cost = Math.ceil((Math.floor(spec.price / 2) * 11) / 10);
    changed.mortgaged = false;
  } else return "invalid";
  const player = match.players[match.turn];
  if (player.cash < cost) return "insufficient";
  player.cash -= cost;
  match.lots[tile] = changed;
  const labels: Partial<Record<Action, string>> = {
    build: "Жақсартылды",
    sell: "Құрылыс сатылды",
    mortgage: "Кепілге қойылды",
    redeem: "Кепілден қайтарылды",
  };
  log(match, `${labels[kind]}: ${spec.name}`);
  return "applied";
}
function tradeable(board: Board, match: Match, tile: number, owner: number): Outcome {
  if (tile < 0 || tile >= board.tiles.length) return "invalid";
  const lot = match.lots[tile];
  if (!lot || lot.owner !== owner || lot.level || lot.mortgaged) return "invalid";
  if (groupIndices(board, tile).some((i) => (match.lots[i]?.level ?? 0) > 0)) return "sell_first";
  return "applied";
}
function transferTrade(board: Board, match: Match, buyer: number, seller: number,
  tile: number, amount: number, giveTile: number) {
  match.players[buyer].cash -= amount;
  match.players[seller].cash += amount;
  match.lots[tile].owner = buyer;
  if (giveTile >= 0) {
    match.lots[giveTile].owner = seller;
    log(match, `Айырбас: ${board.tiles[tile].name} ↔ ${board.tiles[giveTile].name} · ${amount} ◈`);
  } else log(match, `Мәміле: ${board.tiles[tile].name} — ${amount} ₸`);
}
export const offerSender = (offer: Offer) => (offer.proposer ?? -1) >= 0 ? offer.proposer! : offer.buyer;
export const offerRecipient = (offer: Offer) => offerSender(offer) === offer.buyer ? offer.seller : offer.buyer;
function trade(board: Board, room: Room, actor: number, command: Command): Outcome {
  const match = room.match!;
  if (["debt", "finished"].includes(match.phase) || match.players[actor].bankrupt) return "invalid";
  const amount = command.amount ?? 0, giveTile = command.give_tile ?? -1;
  if (["offer", "ask", "counter"].includes(command.kind)) {
    let previous: Offer | undefined;
    let buyer: number, seller: number, tile: number;
    if (command.kind === "counter") {
      previous = match.offers.find((o) => o.id === command.target);
      if (!previous || offerRecipient(previous) !== actor) return "forbidden";
      if (previous.expires < match.round) return "invalid";
      ({ buyer, seller, tile } = previous);
    } else if (command.kind === "ask") {
      buyer = match.players.findIndex((p) => p.id === command.target);
      seller = actor; tile = command.tile ?? -1;
      if (buyer < 0 || buyer === actor) return "invalid";
    } else {
      buyer = actor; tile = command.tile ?? -1;
      const lot = match.lots[tile];
      if (!lot || lot.owner === actor) return "invalid";
      seller = lot.owner;
    }
    if (giveTile < -1 || amount < 0 || (giveTile === -1 && amount < 1)
      || match.players[buyer].bankrupt || match.players[seller].bankrupt) return "invalid";
    const wanted = tradeable(board, match, tile, seller);
    if (wanted !== "applied") return wanted;
    if (giveTile >= 0) {
      const offered = tradeable(board, match, giveTile, buyer);
      if (offered !== "applied") return offered;
    }
    if (match.players[buyer].cash < amount) return "insufficient";
    const recipient = actor === buyer ? seller : buyer;
    if (match.players[recipient].bot) {
      const cost = amount + (giveTile >= 0 ? board.tiles[giveTile].price : 0);
      const accepted = recipient === seller ? cost >= Math.floor(board.tiles[tile].price * 3 / 2)
        : cost <= Math.floor(board.tiles[tile].price * 2 / 3);
      if (!accepted) return "bot_declined";
      transferTrade(board, match, buyer, seller, tile, amount, giveTile);
      return "applied";
    }
    match.offers = match.offers.filter((o) => offerSender(o) !== actor && o.id !== previous?.id);
    match.offers.push({ id: `${room.revision}:${actor}`, buyer, seller, tile, amount,
      expires: match.round + 2, give_tile: giveTile, proposer: actor });
    return "applied";
  }
  const offer = match.offers.find((o) => o.id === command.target);
  if (!offer) return "forbidden";
  if (command.kind === "withdraw") {
    if (offerSender(offer) !== actor) return "forbidden";
    match.offers = match.offers.filter((o) => o.id !== offer.id);
    return "applied";
  }
  if (offerRecipient(offer) !== actor) return "forbidden";
  if (command.kind === "reject") {
    match.offers = match.offers.filter((o) => o.id !== offer.id);
    return "applied";
  }
  if (offer.expires < match.round || match.players[offer.seller].bankrupt) return "invalid";
  const wanted = tradeable(board, match, offer.tile, offer.seller);
  if (wanted !== "applied") return wanted;
  const offeredTile = offer.give_tile ?? -1;
  if (offeredTile >= 0) {
    const offered = tradeable(board, match, offeredTile, offer.buyer);
    if (offered !== "applied") return offered;
  }
  if (match.players[offer.buyer].bankrupt || match.players[offer.buyer].cash < offer.amount) return "insufficient";
  transferTrade(board, match, offer.buyer, offer.seller, offer.tile, offer.amount, offeredTile);
  match.offers = match.offers.filter((o) => o.id !== offer.id);
  return "applied";
}
function botTurn(
  catalog: Catalog,
  scenario: Scenario,
  board: Board,
  match: Match,
  random: RandomBelow,
) {
  const profile =
    catalog.bots.find((b) => b.id === match.players[match.turn].bot) ??
    catalog.bots[0];
  if (match.phase === "roll") {
    for (let i = 0; i < board.tiles.length; i++)
      if (
        match.players[match.turn].cash >=
          board.tiles[i].build_cost + profile.reserve &&
        manage(board, match, "build", i) === "applied"
      )
        break;
    roll(catalog, scenario, board, match, random);
  }
  if (match.phase === "buy") {
    const tile = board.tiles[match.pending],
      player = match.players[match.turn];
    if (player.cash >= tile.price + Math.floor(profile.reserve / 2)) {
      match.lots[match.pending] = {
        owner: match.turn,
        level: 0,
        mortgaged: false,
      };
      player.cash -= tile.price;
      log(match, `${player.name}: сатып алды — ${tile.name}`);
    }
    match.phase = "end";
    match.pending = -1;
  }
  if (match.phase === "debt") {
    for (const kind of ["sell", "mortgage"] as const)
      for (let j = 0; j < board.tiles.length * 4; j++) {
        if (match.players[match.turn].cash >= match.debt!.amount) break;
        let changed = false;
        for (let i = 0; i < board.tiles.length; i++)
          if (manage(board, match, kind, i) === "applied") {
            changed = true;
            break;
          }
        if (!changed) break;
      }
    if (match.debt && match.players[match.turn].cash >= match.debt.amount) {
      settlePayment(catalog, scenario, board, match, random);
      if (["buy", "debt"].includes(match.phase)) { botTurn(catalog, scenario, board, match, random); return; }
    } else bankrupt(board, match);
  }
  if ((match.phase as string) === "end") next(scenario, board, match);
}
function bots(
  catalog: Catalog,
  scenario: Scenario,
  board: Board,
  match: Match,
  random: RandomBelow,
) {
  const limit = scenario.round_limit > 0 ? (scenario.round_limit + 1) * match.players.length : 128;
  for (let i = 0; i < limit; i++) {
    if (match.phase === "finished" || !match.players[match.turn].bot) return;
    botTurn(catalog, scenario, board, match, random);
  }
  if (scenario.round_limit > 0) finish(board, match);
}
export function autoTurn(
  catalog: Catalog,
  room: Room,
  random: RandomBelow,
): Room {
  catalog = activeCatalog(catalog, room);
  if (!room.match || room.match.phase === "finished") return room;
  const result = structuredClone(room),
    scenario = catalog.scenarios.find((s) => s.id === room.scenario_id)!,
    board = boardFor(catalog, room);
  botTurn(catalog, scenario, board, result.match!, random);
  bots(catalog, scenario, board, result.match!, random);
  result.revision++;
  return result;
}
export function applyCommand(
  catalog: Catalog,
  room: Room,
  actor: string,
  command: Command,
  random: RandomBelow,
): Result {
  catalog = activeCatalog(catalog, room);
  const reject = (outcome: Outcome): Result => ({ room, outcome });
  if (command.revision !== room.revision) return reject("stale");
  if (room.closed || !room.seats.some((s) => s.id === actor))
    return reject("forbidden");
  const result = structuredClone(room);
  const applied = (): Result => {
    result.revision++;
    return { room: result, outcome: "applied" };
  };
  if (!result.match) {
    if (command.kind === "ready") {
      const seat = result.seats.find((s) => s.id === actor)!;
      seat.ready = !seat.ready;
      return applied();
    }
    if (actor !== room.host) return reject("forbidden");
    if (command.kind === "configure") {
      if (!catalog.scenarios.some((s) => s.id === command.target))
        return reject("invalid");
      result.scenario_id = command.target!;
      result.seats.forEach((s) => {
        s.ready = !!s.bot || s.id === actor;
      });
      return applied();
    }
    if (command.kind === "add_bot") {
      if (room.seats.length >= 4) return reject("full");
      const bot = catalog.bots.find((b) => b.id === command.target);
      if (!bot || room.seats.some((s) => s.bot === command.target))
        return reject("invalid");
      result.seats.push({
        id: `bot:${room.revision}`,
        name: bot.name,
        color: bot.color,
        bot: bot.id,
        ready: true,
      });
      return applied();
    }
    if (command.kind === "remove_bot") {
      if (!room.seats.some((s) => s.id === command.target && s.bot))
        return reject("invalid");
      result.seats = result.seats.filter((s) => s.id !== command.target);
      return applied();
    }
    if (command.kind === "start") {
      if (
        room.seats.length < 2 ||
        !room.seats.every((s) => s.ready || s.id === room.host)
      )
        return reject("not_ready");
      const scenario = catalog.scenarios.find(
        (s) => s.id === room.scenario_id,
      )!;
      result.seats.sort(
        (a, b) => Number(a.id !== room.host) - Number(b.id !== room.host),
      );
      result.match = {
        catalog_version: catalog.version,
        players: result.seats.map((s) => ({
          id: s.id,
          name: s.name,
          color: s.color,
          bot: s.bot,
          cash: scenario.starting_cash,
          position: 0,
          bankrupt: false,
          skip: 0,
          laps: 0,
        })),
        lots: {},
        turn: 0,
        round: 1,
        phase: "roll",
        dice: [0, 0],
        pending: -1,
        debt: null,
        offers: [],
        log: ["Сәтті партия! Алғашқы жүріс сенікі."],
        moves: [],
        winner: -1,
        classic: boardFor(catalog, result).tiles.length === 40 ? { jailed: {}, doubles: 0, release_steps: 0 } : null,
      };
      return applied();
    }
    return reject("invalid");
  }
  const match = result.match;
  if (match.catalog_version !== catalog.version || match.phase === "finished")
    return reject("invalid");
  const index = match.players.findIndex((p) => p.id === actor),
    board = boardFor(catalog, room),
    scenario = catalog.scenarios.find((s) => s.id === room.scenario_id)!;
  if (["offer", "ask", "counter", "withdraw", "accept", "reject"].includes(command.kind)) {
    const outcome = trade(board, result, index, command);
    if (outcome !== "applied") return reject(outcome);
  } else {
    if (index !== match.turn) return reject("forbidden");
    if (command.kind === "roll" && match.phase === "roll")
      roll(catalog, scenario, board, match, random);
    else if (command.kind === "bail" && match.phase === "roll") {
      if (!match.classic || !(String(index) in match.classic.jailed)) return reject("invalid");
      if (match.players[index].cash < 50) return reject("insufficient");
      match.players[index].cash -= 50; delete match.classic.jailed[index];
      match.classic.doubles = 0; match.classic.release_steps = 0;
    }
    else if (["buy", "pass"].includes(command.kind) && match.phase === "buy") {
      if (command.kind === "buy") {
        const tile = board.tiles[match.pending],
          player = match.players[index];
        if (player.cash < tile.price) return reject("insufficient");
        match.lots[match.pending] = {
          owner: index,
          level: 0,
          mortgaged: false,
        };
        player.cash -= tile.price;
        log(match, `${player.name}: сатып алды — ${tile.name}`);
      }
      match.phase = "end";
      match.pending = -1;
    } else if (command.kind === "end" && match.phase === "end")
      next(scenario, board, match);
    else if (["build", "sell", "mortgage", "redeem"].includes(command.kind)) {
      const outcome = manage(board, match, command.kind, command.tile ?? -1);
      if (outcome !== "applied") return reject(outcome);
    } else if (
      command.kind === "settle" &&
      match.phase === "debt" &&
      match.debt
    ) {
      if (match.players[index].cash < match.debt.amount)
        return reject("insufficient");
      settlePayment(catalog, scenario, board, match, random);
    } else if (command.kind === "bankrupt" && match.phase === "debt") {
      bankrupt(board, match);
      if ((match.phase as string) !== "finished") next(scenario, board, match);
    } else return reject("invalid");
  }
  bots(catalog, scenario, board, match, random);
  return applied();
}
