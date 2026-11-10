export type QuestId = "forest" | "river" | "sky";
export type BuildingId = "yurt" | "well" | "workshop";
export type Period = "week" | "all";
export type Quality = "low" | "high";

export interface Building {
  id: BuildingId;
  name: string;
  level: number;
  wood_cost: number | null;
  stone_cost: number | null;
}

export interface Progress {
  total_xp: number;
  level: number;
  completed_quests: QuestId[];
  completed_today: QuestId[];
  wood: number;
  stone: number;
  buildings: Building[];
}

export interface Run {
  id: string;
  quest_id: QuestId;
  question_index: number;
  total_questions: number;
  points: number;
  complete: boolean;
  question: { prompt: string; options: string[]; tried: string[] } | null;
}

export interface AnswerResult {
  run: Run;
  outcome: "correct" | "wrong" | "replay";
  explanation: string | null;
  progress: Progress;
}

export interface RankEntry {
  rank: number;
  name: string;
  points: number;
  is_self: boolean;
}
export interface Ranking {
  leaders: RankEntry[];
  me: RankEntry | null;
  refresh_seconds: number;
}

export interface QuestGateway {
  readonly practice: boolean;
  progress(): Promise<Progress>;
  start(questId: QuestId): Promise<Run>;
  answer(run: Run, answer: string): Promise<AnswerResult>;
  build(building: Building): Promise<Progress>;
  ranking(period: Period): Promise<Ranking>;
}

export interface WorldTarget {
  id: QuestId | BuildingId;
  kind: "quest" | "building";
  name: string;
  x: number;
  z: number;
  color: string;
}

export const SHRINES: WorldTarget[] = [
  {
    id: "forest",
    kind: "quest",
    name: "Орман рухы",
    x: -11,
    z: -5,
    color: "#b8f486",
  },
  {
    id: "river",
    kind: "quest",
    name: "Бұлақ рухы",
    x: 11,
    z: -4,
    color: "#7de0ef",
  },
  {
    id: "sky",
    kind: "quest",
    name: "Аспан рухы",
    x: 0,
    z: -15,
    color: "#e0b7ff",
  },
];
export const PLOTS: WorldTarget[] = [
  {
    id: "yurt",
    kind: "building",
    name: "Киіз үй",
    x: -4,
    z: 3,
    color: "#efbf77",
  },
  { id: "well", kind: "building", name: "Құдық", x: 4, z: 3, color: "#7de0ef" },
  {
    id: "workshop",
    kind: "building",
    name: "Шеберхана",
    x: 0,
    z: 10,
    color: "#e0b7ff",
  },
];
export const TARGETS = [...SHRINES, ...PLOTS];
