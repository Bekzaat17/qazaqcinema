import assert from "node:assert/strict";
import test from "node:test";
import { playerAppearance, telegramAvatar } from "../src/boardgame/appearance.ts";
import { cellCorners, illustratedPoint } from "../src/boardgame/layout.ts";

test("аватарки допускаются только из Telegram, сторонние адреса не попадают в поле", () => {
  const photo = "https://t.me/i/userpic/320/example.jpg";
  assert.equal(telegramAvatar(photo), photo);
  for (const value of ["javascript:alert(1)", "http://t.me/i/userpic/x.jpg",
    "https://t.me.evil.test/i/userpic/x.jpg", "https://example.com/a.jpg",
    "https://t.me@evil.test/i/userpic/x.jpg", "https://t.me/i/userpic/x.jpg#fragment", "bad"])
    assert.equal(telegramAvatar(value), "");
});

test("у игрока сохраняется выбранный портрет, у ботов свои персонажи", () => {
  assert.deepEqual(playerAppearance({ id: "one", bot: "" }, { one: { portrait: "female" } }),
    { portrait: "female", avatar_url: "" });
  assert.equal(playerAppearance({ id: "two", bot: "balanced" }).portrait, "female");
  assert.equal(playerAppearance({ id: "three", bot: "builder" }).portrait, "male");
  assert.equal(playerAppearance({ id: "old-player", bot: "" }).portrait, "male");
});

test("соседние клетки замкнутого маршрута имеют общую границу", () => {
  for (const count of [16, 24, 40]) {
    for (let index = 0; index < count; index++) {
      const a = cellCorners(index, count);
      const b = cellCorners((index + 1) % count, count);
      const shared = a.filter((p) => b.some((q) => Math.hypot(p.x - q.x, p.y - q.y) < .0001));
      assert.equal(shared.length, 2, `${count} клеток: ${index} → ${(index + 1) % count}`);
    }
    assert.deepEqual(illustratedPoint(0, count, true), illustratedPoint(count, count, true));
  }
});
