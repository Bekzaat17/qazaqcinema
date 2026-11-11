import assert from "node:assert/strict";
import test from "node:test";
import { PracticeQuestGateway } from "../src/quest/practice.ts";
import { dailyTasks, buildingShortfall } from "../src/quest/resources.ts";
import { SHRINES } from "../src/quest/types.ts";

function storage() {
  const data = new Map();
  globalThis.localStorage = { getItem: (key) => data.get(key) ?? null, setItem: (key, value) => data.set(key, value) };
}

test("первые шаги: задание → награда даже с ошибкой → доступная юрта → сохранение", async () => {
  storage();
  const game = new PracticeQuestGateway();
  let progress = await game.progress();
  let tasks = dailyTasks(progress, SHRINES);
  assert.deepEqual(tasks.map((task) => task.locked), [false, true, true]);
  assert.deepEqual(buildingShortfall(progress.buildings[0], progress), { wood: 25, stone: 10, lessons: 1 });
  let run = await game.start(tasks[0].target.id);
  run = (await game.answer(run, "Теңіз")).run;
  run = (await game.answer(run, "Орман")).run;
  run = (await game.answer(run, "Ағаш")).run;
  // Не обещаем ресурсы раньше последнего ответа.
  assert.equal((await game.progress()).wood, 0);
  const reward = await game.answer(run, "Дос");
  assert.equal(reward.run.complete, true);
  progress = reward.progress;
  assert.equal(progress.wood, 25);
  assert.equal(progress.stone, 15);
  assert.equal(progress.total_xp, 80);
  tasks = dailyTasks(progress, SHRINES);
  assert.equal(tasks[0].done, true);
  assert.equal(tasks[1].locked, false);
  assert.deepEqual(buildingShortfall(progress.buildings[0], progress), { wood: 0, stone: 0, lessons: 0 });
  progress = await game.build(progress.buildings[0]);
  assert.equal(progress.buildings[0].level, 1);
  assert.equal(progress.wood, 0);
  assert.equal(progress.stone, 5);
  assert.equal((await new PracticeQuestGateway().progress()).buildings[0].level, 1);
  // Просмотр уже полученной награды не даёт материалы повторно.
  await game.start("forest");
  assert.equal((await game.progress()).wood, 0);
});

test("на новый день открытые духи доступны, расчёт дефицита учитывает оба ресурса и максимальный уровень", async () => {
  storage();
  const progress = await new PracticeQuestGateway().progress();
  progress.completed_quests = ["forest", "river", "sky"];
  assert.ok(dailyTasks(progress, SHRINES).every((task) => !task.locked && !task.done));
  progress.wood = 30;
  progress.stone = 0;
  assert.deepEqual(buildingShortfall(progress.buildings[1], progress), { wood: 0, stone: 20, lessons: 2 });
  assert.deepEqual(buildingShortfall({ ...progress.buildings[0], wood_cost: null, stone_cost: null }, progress), { wood: 0, stone: 0, lessons: 0 });
});
