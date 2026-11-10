import assert from "node:assert/strict";
import test from "node:test";
import { PracticeQuestGateway } from "../src/quest/practice.ts";

class Storage {
  values = new Map();
  getItem(key) {
    return this.values.get(key) ?? null;
  }
  setItem(key, value) {
    this.values.set(key, value);
  }
}

test("тренировка сохраняет аул и не переносит очки в рейтинг", async () => {
  globalThis.localStorage = new Storage();
  const game = new PracticeQuestGateway();
  let run = await game.start("forest");
  run = (await game.answer(run, "Теңіз")).run;
  run = (await game.answer(run, "Орман")).run;
  const duplicate = await game.answer({ ...run, question_index: 0 }, "Орман");
  assert.equal(duplicate.outcome, "replay");
  run = (await game.answer(run, "Ағаш")).run;
  const result = await game.answer(run, "Дос");
  assert.equal(result.run.points, 80);
  const before = await game.progress();
  assert.equal(before.wood, 25);
  await game.build(before.buildings[0]);
  await game.build(before.buildings[0]);
  const reloaded = new PracticeQuestGateway();
  const after = await reloaded.progress();
  assert.equal(after.total_xp, 80);
  assert.equal(after.wood, 0);
  assert.equal(after.stone, 5);
  assert.equal(after.buildings[0].level, 1);
  assert.equal((await reloaded.start("forest")).points, 80);
  assert.deepEqual((await reloaded.ranking("week")).leaders, []);
  await assert.rejects(() => reloaded.build(after.buildings[1]));
});

test("сломанное или недоступное хранилище не блокирует тренировку", async () => {
  globalThis.localStorage = new Storage();
  localStorage.setItem("qazaqquest:practice:v1", "{");
  assert.equal((await new PracticeQuestGateway().progress()).total_xp, 0);
  globalThis.localStorage = {
    getItem() {
      throw new Error("blocked");
    },
    setItem() {
      throw new Error("blocked");
    },
  };
  const game = new PracticeQuestGateway();
  assert.equal((await game.start("forest")).question_index, 0);
});
