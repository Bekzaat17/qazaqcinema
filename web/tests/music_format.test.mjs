import assert from "node:assert/strict";
import test from "node:test";

import { duration, initials, nextIndex, nextPlayable, shuffled } from "../src/music/format.ts";

test("длительность: минуты и часы", () => {
  assert.equal(duration(65), "1:05");
  assert.equal(duration(3725), "1:02:05");
  assert.equal(duration(-3), "0:00");
});

test("инициалы для заглушки обложки", () => {
  assert.equal(initials("Ninety One"), "NO");
  assert.equal(initials(""), "♪");
});

test("очередь: повтор всего и одного трека", () => {
  assert.equal(nextIndex(2, 3, "off"), null);
  assert.equal(nextIndex(2, 3, "all"), 0);
  assert.equal(nextIndex(1, 3, "one"), 1);
});

test("автопереход пропускает треки, которые можно слушать только в Telegram", () => {
  const queue = [{ stream_url: "a" }, { stream_url: null }, { stream_url: "c" }];
  assert.equal(nextPlayable(queue, 0, "off"), 2);
  assert.equal(nextPlayable(queue, 2, "off"), null);
  assert.equal(nextPlayable(queue, 2, "all"), 0);
  assert.equal(nextPlayable([{ stream_url: null }], 0, "all"), null);
});

test("перемешивание оставляет текущий трек первым и не теряет треки", () => {
  const items = [1, 2, 3, 4, 5];
  const result = shuffled(items, 2, () => 0.5);
  assert.equal(result[0], 3);
  assert.deepEqual([...result].sort(), items);
});
