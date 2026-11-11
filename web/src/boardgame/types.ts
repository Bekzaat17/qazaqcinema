import type { PlayerAppearance } from "../ui-kit/PlayerAvatar";
export interface Tile {
  street?: string;
  street_sprite?: number;
  landmark?: string;
  sprite?: number;
  id: string;
  name: string;
  kind: string;
  group: string;
  color: string;
  price: number;
  rents: number[];
  build_cost: number;
  amount: number;
}
export interface Board {
  miniature_atlas?: string;
  street_atlas?: string;
  illustration?: string;
  thumbnail?: string;
  id: string;
  name: string;
  subtitle: string;
  biome: string;
  ground: string;
  sky: string;
  accent: string;
  tiles: Tile[];
}
export interface Scenario {
  id: string;
  board: string;
  name: string;
  story: string;
  round_limit: number; // 0 — до одного оставшегося участника.
  starting_cash: number;
  salary: number;
  tax_multiplier: number;
  event_multiplier: number;
  reward: number;
}
export interface Card {
  id: string;
  text: string;
  amount: number;
  move: number | null;
  skip: number;
  deck?: string;
}
export interface Bot {
  id: string;
  name: string;
  reserve: number;
  color: string;
}
export interface Catalog {
  version: number;
  boards: Board[];
  scenarios: Scenario[];
  cards: Card[];
  bots: Bot[];
  legacy_catalogs?: Catalog[];
}
export type Phase = "roll" | "buy" | "end" | "debt" | "finished";
export type Action =
  | "start"
  | "configure"
  | "add_bot"
  | "remove_bot"
  | "ready"
  | "roll"
  | "bail"
  | "buy"
  | "pass"
  | "end"
  | "build"
  | "sell"
  | "mortgage"
  | "redeem"
  | "settle"
  | "bankrupt"
  | "offer"
  | "ask"
  | "counter"
  | "withdraw"
  | "accept"
  | "reject"
  | "timeout";
export type Outcome =
  | "channel_required"
  | "applied"
  | "stale"
  | "forbidden"
  | "invalid"
  | "insufficient"
  | "group_required"
  | "even_building"
  | "sell_first"
  | "not_ready"
  | "full"
  | "bot_declined"
  | "too_early";
export interface Seat {
  id: string;
  name: string;
  color: string;
  bot: string;
  ready: boolean;
}
export interface Player {
  id: string;
  name: string;
  color: string;
  bot: string;
  cash: number;
  position: number;
  bankrupt: boolean;
  skip: number;
  laps: number;
}
export interface Lot {
  owner: number;
  level: number;
  mortgaged: boolean;
}
export interface Debt {
  amount: number;
  creditor: number;
}
export interface Move {
  player: number;
  start: number;
  steps: number;
  end: number;
  dice: [number, number];
}
export interface Offer {
  id: string;
  buyer: number;
  seller: number;
  tile: number;
  amount: number;
  expires: number;
  give_tile?: number;
  proposer?: number;
}
export interface ClassicState { jailed: Record<string, number>; doubles: number; release_steps: number }
export interface Match {
  classic?: ClassicState | null;
  catalog_version: number;
  players: Player[];
  lots: Record<string, Lot>;
  turn: number;
  round: number;
  phase: Phase;
  dice: [number, number];
  pending: number;
  debt: Debt | null;
  offers: Offer[];
  log: string[];
  moves: Move[];
  winner: number;
}
export interface Room {
  appearances?: Record<string, PlayerAppearance>;
  revision: number;
  host: string;
  scenario_id: string;
  seats: Seat[];
  match: Match | null;
  closed: boolean;
}
export interface Command {
  revision: number;
  kind: Action;
  target?: string;
  tile?: number;
  amount?: number;
  give_tile?: number;
}
export interface Result {
  room: Room;
  outcome: Outcome;
}
export interface RoomView {
  blocked_seats?: string[];
  is_public?: boolean;
  appearances?: Record<string, PlayerAppearance>;
  code: string;
  room: Room;
  me: string;
  deadline: string | null;
  server_time: string;
  outcome: Outcome;
}
export type RandomBelow = (maximum: number) => number;

export interface PublicRoom { code: string; host_name: string; scenario_id: string; players: number }
export interface ActiveRoom extends PublicRoom { started: boolean; is_public: boolean }
export interface GameAccess { games_started: number; free_left: number; allowed: boolean; channel_url: string }
export interface GameHistory { code: string; scenario_id: string; board_id: string; rounds: number; finished_at: string; winner_name: string; player_count: number; capital: number; won: boolean }
export interface GameRank { rank: number; name: string; played: number; wins: number; is_me: boolean }
export interface GameRanking { entries: GameRank[]; me: GameRank | null }
