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
  round_limit: number;
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
}
export type Phase = "roll" | "buy" | "end" | "debt" | "finished";
export type Action =
  | "start"
  | "configure"
  | "add_bot"
  | "remove_bot"
  | "ready"
  | "roll"
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
  | "accept"
  | "reject"
  | "timeout";
export type Outcome =
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
}
export interface Match {
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
}
export interface Result {
  room: Room;
  outcome: Outcome;
}
export interface RoomView {
  code: string;
  room: Room;
  me: string;
  deadline: string | null;
  server_time: string;
  outcome: Outcome;
}
export type RandomBelow = (maximum: number) => number;
