import assert from "node:assert/strict";
import test from "node:test";
import { roomCode, roomLink, shareRoomLink } from "../src/boardgame/rooms.ts";

test("код комнаты принимается отдельно и из приглашения Telegram", () => {
  for (const input of ["a1b2c3d4e5", " A1B2C 3D4E5 ", "quest_room_a1b2c3d4e5", "https://t.me/qazaqcinema_bot?startapp=quest_room_A1B2C3D4E5", "https://app.test/quest?room=A1B2C3D4E5"])
    assert.equal(roomCode(input), "A1B2C3D4E5");
  for (const input of ["", "123", "javascript:alert(1)", "A1B2C3D4E5garbage", "https://t.me/bot?startapp=quest_rooms"])
    assert.equal(roomCode(input), "");
});

test("приглашение открывает правильную комнату, шаринг не теряет параметры ссылки", () => {
  const link = roomLink("https://t.me/bot", "A1B2C3D4E5");
  assert.equal(roomCode(link), "A1B2C3D4E5");
  const share = new URL(shareRoomLink("https://t.me/bot", "A1B2C3D4E5"));
  assert.equal(share.hostname, "t.me");
  assert.equal(share.pathname, "/share/url");
  assert.equal(share.searchParams.get("url"), link);
  assert.match(share.searchParams.get("text"), /A1B2C3D4E5/);
});
