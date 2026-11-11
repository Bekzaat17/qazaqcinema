import assert from "node:assert/strict";
import test from "node:test";
import { PracticeTrials } from "../src/boardgame/trials.ts";

test("три гостевых старта сохраняются между входами, четвёртый требует Telegram", () => {
  const values = new Map();
  globalThis.localStorage = { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
  const trials = new PracticeTrials();
  for (let i = 0; i < 3; i++) { assert.equal(trials.access().allowed, true); trials.recordStart(); }
  assert.equal(trials.access().allowed, false);
  assert.equal(new PracticeTrials().access().free_left, 0);
});
