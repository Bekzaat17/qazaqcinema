import { api, request } from "../lib/api";
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

export class HttpQuestGateway implements QuestGateway {
  readonly practice = false;
  private ready: Promise<unknown> | null = null;

  private async call<T>(path: string, body?: unknown): Promise<T> {
    this.ready ??= api.auth().catch((error: unknown) => {
      this.ready = null;
      throw error;
    });
    await this.ready;
    return request<T>(
      `/api/quest${path}`,
      body === undefined
        ? undefined
        : {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          },
    );
  }

  progress() {
    return this.call<Progress>("/progress");
  }
  start(questId: QuestId) {
    return this.call<Run>("/runs", { quest_id: questId });
  }
  answer(run: Run, answer: string) {
    return this.call<AnswerResult>(`/runs/${run.id}/answer`, {
      question_index: run.question_index,
      answer,
    });
  }
  build(building: Building) {
    return this.call<Progress>("/build", {
      building_id: building.id,
      target_level: building.level + 1,
    });
  }
  ranking(period: Period) {
    return this.call<Ranking>(`/ranking?period=${period}`);
  }
}
