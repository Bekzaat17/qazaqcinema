import type { Building, Progress, QuestId, WorldTarget } from "./types";

export const LESSON_REWARD = { wood: 25, stone: 15, maxXp: 100 };

export function dailyTasks(progress: Progress, shrines: readonly WorldTarget[]) {
  return shrines.map((target, index) => ({
    target,
    done: progress.completed_today.includes(target.id as QuestId),
    locked: index > 0 && !progress.completed_quests.includes(shrines[index - 1].id as QuestId),
    prerequisite: index > 0 ? shrines[index - 1].name : "",
  }));
}

export function buildingShortfall(building: Building, progress: Progress) {
  const wood = Math.max(0, (building.wood_cost ?? 0) - progress.wood);
  const stone = Math.max(0, (building.stone_cost ?? 0) - progress.stone);
  return {
    wood,
    stone,
    lessons: Math.max(Math.ceil(wood / LESSON_REWARD.wood), Math.ceil(stone / LESSON_REWARD.stone)),
  };
}
