import assert from "node:assert/strict";
import test from "node:test";
import { isQuestStartParam } from "../src/quest/startParam.ts";

test("Telegram-приглашения и создание комнат открывают игровой раздел", () => {
  for (const value of ["quest", "quest_rooms", "quest_create", "quest_create_public", "quest_room_A1B2C3D4E5"])
    assert.equal(isQuestStartParam(value), true);
  for (const value of [null, "", "m_42", "quest_room_bad", "quest_unknown"])
    assert.equal(isQuestStartParam(value), false);
});
