import type { PlayerAppearance } from "../ui-kit/PlayerAvatar";
import { PracticeTrials } from "./trials";
import { api, request } from "../lib/api";
import { activeCatalog, applyCommand, autoTurn } from "./rules.ts";
import type { Catalog, Command, Room, RoomView, PublicRoom, ActiveRoom, GameHistory, GameRanking, GameAccess } from "./types.ts";

const KEY = "qazaqquest:boardgame:v2";
export const LIVE_ROOM_KEY = "qazaqquest:live-room:v2";
export interface GameGateway {
  access(): Promise<GameAccess>;
  readonly practice: boolean;
  create(name: string, scenario: string, appearance?: PlayerAppearance, isPublic?: boolean): Promise<RoomView>;
  publicRooms(signal?: AbortSignal): Promise<PublicRoom[]>;
  myRooms(signal?: AbortSignal): Promise<ActiveRoom[]>;
  setVisibility(code: string, isPublic: boolean): Promise<RoomView>;
  history(offset?: number): Promise<GameHistory[]>;
  ranking(): Promise<GameRanking>;
  join(name: string, code: string, appearance?: PlayerAppearance): Promise<RoomView>;
  view(code: string, after?: number, signal?: AbortSignal): Promise<RoomView>;
  act(code: string, command: Command): Promise<RoomView>;
  leave(code: string): Promise<void>;
  setAppearance(code: string, appearance: PlayerAppearance): Promise<RoomView>;
}
function below(maximum: number): number {
  const buffer = new Uint32Array(1);
  const limit = Math.floor(0x100000000 / maximum) * maximum;
  do {
    crypto.getRandomValues(buffer);
  } while (buffer[0] >= limit);
  return buffer[0] % maximum;
}
function validRoom(raw: unknown, catalog: Catalog): raw is Room {
  if (!raw || typeof raw !== "object") return false;
  const room = raw as Room;
  catalog = activeCatalog(catalog, room);
  if (
    !Number.isSafeInteger(room.revision) ||
    room.revision < 0 ||
    !catalog.scenarios.some((s) => s.id === room.scenario_id) ||
    !Array.isArray(room.seats) ||
    room.seats.length < 1 ||
    room.seats.length > 4 ||
    new Set(room.seats.map((s) => s.id)).size !== room.seats.length ||
    !room.seats.every(
      (s) =>
        typeof s.id === "string" &&
        typeof s.name === "string" &&
        s.name.length <= 24 &&
        /^#[a-f0-9]{6}$/i.test(s.color) &&
        typeof s.ready === "boolean" &&
        (s.bot === "" || catalog.bots.some((b) => b.id === s.bot)),
    ) ||
    !room.seats.some((s) => s.id === room.host) ||
    typeof room.closed !== "boolean"
  )
    return false;
  const m = room.match;
  catalog = activeCatalog(catalog, room);
  if (m === null) return true;
  const scenario = catalog.scenarios.find((s) => s.id === room.scenario_id)!;
  const board = catalog.boards.find((b) => b.id === scenario.board)!;
  if (
    !m ||
    m.catalog_version !== catalog.version ||
    (m.classic != null && (typeof m.classic !== "object" || !m.classic.jailed
      || typeof m.classic.jailed !== "object" || !Number.isInteger(m.classic.doubles)
      || m.classic.doubles < 0 || m.classic.doubles > 2 || !Number.isInteger(m.classic.release_steps)
      || m.classic.release_steps < 0 || m.classic.release_steps > 12)) ||
    !Array.isArray(m.players) ||
    m.players.length !== room.seats.length ||
    !m.players.every(
      (p) =>
        room.seats.some((s) => s.id === p.id) &&
        Number.isSafeInteger(p.cash) &&
        p.cash >= 0 &&
        p.cash < 1e9 &&
        Number.isInteger(p.position) &&
        p.position >= 0 &&
        p.position < board.tiles.length &&
        typeof p.bankrupt === "boolean" &&
        Number.isInteger(p.skip) &&
        p.skip >= 0 &&
        Number.isInteger(p.laps) &&
        p.laps >= 0,
    ) ||
    !Number.isInteger(m.turn) ||
    m.turn < 0 ||
    m.turn >= m.players.length ||
    !Number.isSafeInteger(m.round) ||
    m.round < 1 ||
    (scenario.round_limit > 0 && m.round > scenario.round_limit + 1) ||
    !["roll", "buy", "end", "debt", "finished"].includes(m.phase)
  )
    return false;
  if (
    !m.lots ||
    typeof m.lots !== "object" ||
    !Object.entries(m.lots).every(
      ([key, lot]) =>
        /^\d+$/.test(key) &&
        +key < board.tiles.length &&
        ["property", "station", "utility"].includes(board.tiles[+key].kind) &&
        Number.isInteger(lot.owner) &&
        lot.owner >= 0 &&
        lot.owner < m.players.length &&
        Number.isInteger(lot.level) &&
        lot.level >= 0 &&
        lot.level < board.tiles[+key].rents.length &&
        typeof lot.mortgaged === "boolean",
    )
  )
    return false;
  return (
    Array.isArray(m.dice) &&
    m.dice.length === 2 &&
    m.dice.every((n) => Number.isInteger(n) && n >= 0 && n <= 6) &&
    Number.isInteger(m.pending) &&
    m.pending >= -1 &&
    m.pending < board.tiles.length &&
    Array.isArray(m.log) &&
    m.log.length <= 12 &&
    m.log.every((s) => typeof s === "string") &&
    Array.isArray(m.moves) &&
    m.moves.length <= 8 &&
    m.moves.every(
      (move) =>
        Number.isInteger(move.player) &&
        move.player >= 0 &&
        move.player < m.players.length &&
        Number.isInteger(move.start) &&
        move.start >= 0 &&
        move.start < board.tiles.length &&
        Number.isInteger(move.steps) &&
        move.steps >= 0 &&
        move.steps <= 40 &&
        Number.isInteger(move.end) &&
        move.end >= 0 &&
        move.end < board.tiles.length &&
        Array.isArray(move.dice) &&
        move.dice.length === 2,
    ) &&
    Array.isArray(m.offers) &&
    m.offers.length <= 4 &&
    m.offers.every(
      (o) =>
        typeof o.id === "string" &&
        Number.isInteger(o.buyer) &&
        Number.isInteger(o.seller) &&
        o.buyer >= 0 &&
        o.buyer < m.players.length &&
        o.seller >= 0 &&
        o.seller < m.players.length &&
        (o.give_tile === undefined || (Number.isInteger(o.give_tile) && o.give_tile >= -1 && o.give_tile < board.tiles.length)) &&
        (o.proposer === undefined || o.proposer === -1 || o.proposer === o.buyer || o.proposer === o.seller) &&
        Number.isInteger(o.tile) &&
        o.tile >= 0 &&
        o.tile < board.tiles.length &&
        Number.isInteger(o.amount) &&
        o.amount >= 0 && (o.amount > 0 || (o.give_tile ?? -1) >= 0),
    ) &&
    Number.isInteger(m.winner) &&
    m.winner >= -1 &&
    m.winner < m.players.length &&
    (m.debt === null ||
      (Number.isSafeInteger(m.debt.amount) &&
        m.debt.amount > 0 &&
        Number.isInteger(m.debt.creditor) &&
        m.debt.creditor >= -1 &&
        m.debt.creditor < m.players.length))
  );
}
export class PracticeGameGateway implements GameGateway {
  private trials = new PracticeTrials();
  async access() { return this.trials.access(); }
  readonly practice = true;
  async publicRooms() { return []; }
  async myRooms() { return []; }
  async history() { return []; }
  async ranking(): Promise<GameRanking> { return { entries: [], me: null }; }
  async setVisibility() { return this.output(); }
  private room: Room | null = null;
  constructor(private catalog: Catalog) {
    try {
      const raw = JSON.parse(localStorage.getItem(KEY) ?? "null");
      if (validRoom(raw, catalog)) this.room = raw;
    } catch {
      /* Запрет хранилища не мешает локальной партии. */
    }
  }
  private output(): RoomView {
    if (!this.room) throw new Error("missing");
    return {
      code: "PRACTICE",
      room: structuredClone(this.room),
      appearances: structuredClone(this.room.appearances ?? {}),
      me: this.room.host,
      deadline: null,
      server_time: new Date().toISOString(),
      outcome: "applied",
    };
  }
  private save() {
    try {
      localStorage.setItem(KEY, JSON.stringify(this.room));
    } catch {
      /* Партия остаётся в памяти приватного WebView. */
    }
  }
  async create(name: string, scenario: string, appearance?: PlayerAppearance) {
    this.room = {
      revision: 0,
      appearances: { you: appearance ?? {} },
      host: "you",
      scenario_id: scenario,
      seats: [{ id: "you", name, color: "#479e8b", bot: "", ready: true }],
      match: null,
      closed: false,
    };
    this.save();
    return this.output();
  }
  async join(_name: string, _code: string): Promise<RoomView> {
    throw new Error("telegram_required");
  }
  async view(_code: string, _after?: number, _signal?: AbortSignal) {
    return this.output();
  }
  async act(_code: string, command: Command) {
    if (!this.room) throw new Error("missing");
    if (command.kind === "start" && !this.room.match && command.revision === this.room.revision
      && !this.trials.access().allowed) return { ...this.output(), outcome: "channel_required" as const, blocked_seats: [this.room.host] };
    if (command.kind === "timeout" && this.room.match?.phase !== "finished"
      && this.room.match?.players[this.room.match.turn].bot) {
      if (command.revision !== this.room.revision) return { ...this.output(), outcome: "stale" as const };
      this.room = autoTurn(this.catalog, this.room, below);
      this.save();
      return this.output();
    }
    const result = applyCommand(
      this.catalog,
      this.room,
      this.room.host,
      command,
      below,
    );
    this.room = result.room;
    if (command.kind === "start" && result.outcome === "applied" && this.room.match) this.trials.recordStart();
    this.save();
    return { ...this.output(), outcome: result.outcome };
  }
  async setAppearance(_code: string, appearance: PlayerAppearance) {
    if (!this.room) throw new Error("missing");
    this.room.appearances = { ...this.room.appearances, [this.room.host]: appearance };
    this.save();
    return this.output();
  }
  async leave(_code: string) {
    this.room = null;
    try {
      localStorage.removeItem(KEY);
    } catch {
      /* Нечего сохранять. */
    }
  }
}
export class HttpGameGateway implements GameGateway {
  async access() {
    await this.auth();
    return request<GameAccess>("/api/boardgame/access");
  }
  readonly practice = false;
  private ready: Promise<unknown> | null = null;
  private async auth() {
    this.ready ??= api.auth().catch((error: unknown) => {
      this.ready = null;
      throw error;
    });
    await this.ready;
  }
  async publicRooms(signal?: AbortSignal) {
    await this.auth();
    return request<PublicRoom[]>("/api/boardgame/rooms", { signal });
  }
  async myRooms(signal?: AbortSignal) {
    await this.auth();
    return request<ActiveRoom[]>("/api/boardgame/rooms/mine", { signal });
  }
  async history(offset = 0) {
    await this.auth();
    return request<GameHistory[]>(`/api/boardgame/history?offset=${offset}`);
  }
  async ranking() {
    await this.auth();
    return request<GameRanking>("/api/boardgame/ranking");
  }
  async setVisibility(code: string, isPublic: boolean) {
    await this.auth();
    return request<RoomView>(`/api/boardgame/rooms/${code}/visibility`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_public: isPublic }),
    });
  }
  async create(name: string, scenario: string, appearance?: PlayerAppearance, isPublic = false) {
    await this.auth();
    return request<RoomView>("/api/boardgame/rooms", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, scenario_id: scenario, is_public: isPublic, ...appearance }),
    });
  }
  async join(name: string, code: string, appearance?: PlayerAppearance) {
    await this.auth();
    return request<RoomView>(`/api/boardgame/rooms/${code}/join`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, ...appearance }),
    });
  }
  async view(code: string, after?: number, signal?: AbortSignal) {
    await this.auth();
    return request<RoomView>(
      `/api/boardgame/rooms/${code}${after === undefined ? "" : `?after=${after}`}`,
      { signal },
      { timeoutMs: 35_000 },
    );
  }
  async act(code: string, command: Command) {
    await this.auth();
    return request<RoomView>(`/api/boardgame/rooms/${code}/command`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(command),
    });
  }
  async setAppearance(code: string, appearance: PlayerAppearance) {
    await this.auth();
    return request<RoomView>(`/api/boardgame/rooms/${code}/appearance`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(appearance),
    });
  }
  async leave(code: string) {
    await this.auth();
    await request(`/api/boardgame/rooms/${code}/leave`, { method: "POST" });
  }
}
