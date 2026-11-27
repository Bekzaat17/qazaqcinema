import assert from "node:assert/strict";
import test from "node:test";

import { duration, fromHere, initials, moved } from "../src/music/format.ts";

test("длительность: минуты и часы", () => {
  assert.equal(duration(65), "1:05");
  assert.equal(duration(3725), "1:02:05");
  assert.equal(duration(-3), "0:00");
});

test("инициалы для заглушки обложки", () => {
  assert.equal(initials("Ninety One"), "NO");
  assert.equal(initials(""), "♪");
});

test("играть отсюда: трек и следующие, не больше предела", () => {
  assert.deepEqual(fromHere([1, 2, 3, 4], 1, 50), [2, 3, 4]);
  assert.deepEqual(fromHere([1, 2, 3, 4], 0, 2), [1, 2]);
  assert.deepEqual(fromHere([1, 2], 5, 50), []);
});

test("реттеу: сосед меняется местами, края не ломаются", () => {
  assert.deepEqual(moved([1, 2, 3], 0, 1), [2, 1, 3]);
  assert.deepEqual(moved([1, 2, 3], 2, -1), [1, 3, 2]);
  assert.deepEqual(moved([1, 2, 3], 0, -1), [1, 2, 3]);
  assert.deepEqual(moved([1, 2, 3], 2, 1), [1, 2, 3]);
});
