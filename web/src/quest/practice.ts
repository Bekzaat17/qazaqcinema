// Гостевая тренировка изолирована от серверного кошелька и никогда не попадает в рейтинг.
import type {
  AnswerResult,
  Building,
  Period,
  Progress,
  QuestGateway,
  QuestId,
  Ranking,
  Run,
} from "./types";

interface Lesson {
  prompt: string;
  options: string[];
  correct: string;
  explanation: string;
}
const LESSONS: Record<QuestId, Lesson[]> = {
  forest: [
    {
      prompt: "«Лес» қазақша қалай аталады?",
      options: ["Орман", "Теңіз", "Қала"],
      correct: "Орман",
      explanation: "Орман — лес. Ағаш — дерево.",
    },
    {
      prompt: "«Дерево» сөзінің аудармасын тап.",
      options: ["Тас", "Ағаш", "Бұлт"],
      correct: "Ағаш",
      explanation: "Ағаштар ауаны тазартады.",
    },
    {
      prompt: "Қай сөз «друг» дегенді білдіреді?",
      options: ["Жол", "Түн", "Дос"],
      correct: "Дос",
      explanation: "Дос — друг. Достық — үлкен байлық.",
    },
  ],
  river: [
    {
      prompt: "«Вода» сөзінің аудармасын тап.",
      options: ["От", "Су", "Жер"],
      correct: "Су",
      explanation: "Су — тіршілік көзі.",
    },
    {
      prompt: "«Родник» қазақша қалай аталады?",
      options: ["Бұлақ", "Тау", "Дала"],
      correct: "Бұлақ",
      explanation: "Бұлақ — жер астынан шығатын су көзі.",
    },
    {
      prompt: "«Река» қазақша қалай аталады?",
      options: ["Көл", "Жаңбыр", "Өзен"],
      correct: "Өзен",
      explanation: "Өзен — река, көл — озеро.",
    },
  ],
  sky: [
    {
      prompt: "«Небо» қазақша қалай аталады?",
      options: ["Аспан", "Орман", "Бұлақ"],
      correct: "Аспан",
      explanation: "Аспан — небо.",
    },
    {
      prompt: "«Жұлдыз» сөзінің аудармасын тап.",
      options: ["Луна", "Солнце", "Звезда"],
      correct: "Звезда",
      explanation: "Жұлдыз — звезда, ай — луна.",
    },
    {
      prompt: "«Арман» орысша қалай аталады?",
      options: ["Мечта", "Дождь", "Дорога"],
      correct: "Мечта",
      explanation: "Арманыңа қарай қадам жаса!",
    },
  ],
};
const COSTS = {
  yurt: [
    [25, 10],
    [45, 25],
    [70, 40],
  ],
  well: [
    [20, 20],
    [40, 35],
    [60, 50],
  ],
  workshop: [
    [35, 15],
    [55, 30],
    [80, 45],
  ],
};
const KEY = "qazaqquest:practice:v1";
const today = () =>
  new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Almaty" }).format(
    new Date(),
  );

function initial(): Progress {
  return {
    total_xp: 0,
    level: 1,
    completed_quests: [],
    completed_today: [],
    wood: 0,
    stone: 0,
    buildings: [
      { id: "yurt", name: "Киіз үй", level: 0, wood_cost: 25, stone_cost: 10 },
      { id: "well", name: "Құдық", level: 0, wood_cost: 20, stone_cost: 20 },
      {
        id: "workshop",
        name: "Шеберхана",
        level: 0,
        wood_cost: 35,
        stone_cost: 15,
      },
    ],
  };
}

export class PracticeQuestGateway implements QuestGateway {
  readonly practice = true;
  private state = initial();
  private day = today();
  private runs: Partial<Record<QuestId, Run>> = {};
  private rewards: Partial<Record<QuestId, number>> = {};

  constructor() {
    try {
      const raw = JSON.parse(localStorage.getItem(KEY) ?? "null");
      if (
        raw?.version === 1 &&
        typeof raw.day === "string" &&
        Number.isInteger(raw.state?.total_xp) &&
        raw.state.total_xp >= 0 &&
        Number.isInteger(raw.state?.level) &&
        Array.isArray(raw.state?.completed_quests) &&
        Array.isArray(raw.state?.completed_today) &&
        [...raw.state.completed_quests, ...raw.state.completed_today].every(
          (id: string) => id in LESSONS,
        ) &&
        Array.isArray(raw.state?.buildings) &&
        raw.state.buildings.length === 3 &&
        raw.state.buildings.every(
          (b: Building) =>
            b.id in COSTS &&
            Number.isInteger(b.level) &&
            b.level >= 0 &&
            b.level <= 3,
        ) &&
        Number.isFinite(raw.state.wood) &&
        Number.isFinite(raw.state.stone)
      ) {
        this.state = raw.state as Progress;
        this.day = raw.day;
        for (const id of ["forest", "river", "sky"] as const) {
          if (
            Number.isInteger(raw.rewards?.[id]) &&
            raw.rewards[id] >= 0 &&
            raw.rewards[id] <= 100
          )
            this.rewards[id] = raw.rewards[id];
        }
        // Восстанавливаем только прогресс; прерванный учебный квиз можно начать заново.
      }
    } catch {
      /* Хранилище может быть запрещено: тренировка всё равно работает в памяти. */
    }
  }

  private save() {
    try {
      localStorage.setItem(
        KEY,
        JSON.stringify({
          version: 1,
          day: this.day,
          state: this.state,
          rewards: this.rewards,
        }),
      );
    } catch {
      /* Приватный WebView: остаётся сессия в памяти. */
    }
  }
  private rollover() {
    if (this.day !== today()) {
      this.day = today();
      this.runs = {};
      this.rewards = {};
      this.state.completed_today = [];
      this.save();
    }
  }
  async progress(): Promise<Progress> {
    this.rollover();
    return structuredClone(this.state);
  }
  async start(questId: QuestId): Promise<Run> {
    this.rollover();
    const ids: QuestId[] = ["forest", "river", "sky"];
    if (
      ids
        .slice(0, ids.indexOf(questId))
        .some((id) => !this.state.completed_quests.includes(id))
    )
      throw new Error("Алдыңғы рухты оят.");
    if (!this.runs[questId]) {
      const complete = this.state.completed_today.includes(questId);
      const lesson = LESSONS[questId][0];
      this.runs[questId] = {
        id: `practice:${this.day}:${questId}`,
        quest_id: questId,
        question_index: complete ? 3 : 0,
        total_questions: 3,
        points: complete ? (this.rewards[questId] ?? 0) : 0,
        complete,
        question: complete
          ? null
          : { prompt: lesson.prompt, options: lesson.options, tried: [] },
      };
    }
    return structuredClone(this.runs[questId]!);
  }
  async answer(input: Run, answer: string): Promise<AnswerResult> {
    this.rollover();
    const run = this.runs[input.quest_id];
    if (!run || input.id !== run.id)
      throw new Error("Жаңа күн басталды. Сынақты қайта аш.");
    let outcome: AnswerResult["outcome"] = "replay";
    let explanation: string | null = null;
    if (
      !run.complete &&
      input.question_index === run.question_index &&
      run.question &&
      !run.question.tried.includes(answer)
    ) {
      const lesson = LESSONS[run.quest_id][run.question_index];
      if (!lesson.options.includes(answer)) throw new Error("Жауапты таңда.");
      if (answer !== lesson.correct) {
        outcome = "wrong";
        run.question.tried.push(answer);
      } else {
        outcome = "correct";
        explanation = lesson.explanation;
        run.points += run.question.tried.length ? 10 : 30;
        run.question_index += 1;
        run.complete = run.question_index === 3;
        if (run.complete) {
          run.points += 10;
          run.question = null;
          this.rewards[run.quest_id] = run.points;
          this.state.total_xp += run.points;
          this.state.level = 1 + Math.floor(this.state.total_xp / 300);
          this.state.wood += 25;
          this.state.stone += 15;
          this.state.completed_today.push(run.quest_id);
          if (!this.state.completed_quests.includes(run.quest_id))
            this.state.completed_quests.push(run.quest_id);
        } else {
          const next = LESSONS[run.quest_id][run.question_index];
          run.question = {
            prompt: next.prompt,
            options: next.options,
            tried: [],
          };
        }
      }
    }
    this.save();
    return {
      run: structuredClone(run),
      outcome,
      explanation,
      progress: await this.progress(),
    };
  }
  async build(input: Building): Promise<Progress> {
    const building = this.state.buildings.find((b) => b.id === input.id)!;
    if (building.level !== input.level) return this.progress();
    const cost = COSTS[building.id][building.level];
    if (!cost || this.state.wood < cost[0] || this.state.stone < cost[1])
      throw new Error("Материал жеткіліксіз. Рухтардың тапсырмаларын орында.");
    this.state.wood -= cost[0];
    this.state.stone -= cost[1];
    building.level += 1;
    const next = COSTS[building.id][building.level];
    building.wood_cost = next?.[0] ?? null;
    building.stone_cost = next?.[1] ?? null;
    this.save();
    return this.progress();
  }
  async ranking(_period: Period): Promise<Ranking> {
    return { leaders: [], me: null, refresh_seconds: 300 };
  }
}
