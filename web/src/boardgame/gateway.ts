import { api, request } from "../lib/api";
import { applyCommand } from "./rules.ts";
import type { Catalog, Command, Room, RoomView } from "./types.ts";

const KEY = "qazaqquest:boardgame:v2";
export const LIVE_ROOM_KEY = "qazaqquest:live-room:v2";
export interface GameGateway {
  readonly practice: boolean;
  create(name: string, scenario: string): Promise<RoomView>;
  join(name: string, code: string): Promise<RoomView>;
  view(code: string, after?: number, signal?: AbortSignal): Promise<RoomView>;
  act(code: string, command: Command): Promise<RoomView>;
  leave(code: string): Promise<void>;
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
  if (m === null) return true;
  const board = catalog.boards.find(
    (b) =>
      b.id === catalog.scenarios.find((s) => s.id === room.scenario_id)?.board,
  )!;
  if (
    !m ||
    m.catalog_version !== catalog.version ||
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
    !Number.isInteger(m.round) ||
    m.round < 1 ||
    m.round > 51 ||
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
        ["property", "station"].includes(board.tiles[+key].kind) &&
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
        Number.isInteger(o.tile) &&
        o.tile >= 0 &&
        o.tile < board.tiles.length &&
        Number.isInteger(o.amount) &&
        o.amount > 0,
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
  readonly practice = true;
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
  async create(name: string, scenario: string) {
    this.room = {
      revision: 0,
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
    const result = applyCommand(
      this.catalog,
      this.room,
      this.room.host,
      command,
      below,
    );
    this.room = result.room;
    this.save();
    return { ...this.output(), outcome: result.outcome };
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
  readonly practice = false;
  private ready: Promise<unknown> | null = null;
  private async auth() {
    this.ready ??= api.auth().catch((error: unknown) => {
      this.ready = null;
      throw error;
    });
    await this.ready;
  }
  async create(name: string, scenario: string) {
    await this.auth();
    return request<RoomView>("/api/boardgame/rooms", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, scenario_id: scenario }),
    });
  }
  async join(name: string, code: string) {
    await this.auth();
    return request<RoomView>(`/api/boardgame/rooms/${code}/join`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
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
  async leave(code: string) {
    await this.auth();
    await request(`/api/boardgame/rooms/${code}/leave`, { method: "POST" });
  }
}
