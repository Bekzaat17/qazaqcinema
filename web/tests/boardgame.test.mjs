import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import {
  applyCommand,
  autoTurn,
  netWorth,
  boardFor,
} from "../src/boardgame/rules.ts";

const catalog = JSON.parse(
  readFileSync(
    new URL("../public/boardgame/catalog.json", import.meta.url),
    "utf8",
  ),
);
const contract = JSON.parse(
  readFileSync(
    new URL("../../tests/fixtures/boardgame_contract.json", import.meta.url),
    "utf8",
  ),
);
const initial = (scenario) => ({
  revision: 0,
  host: "human",
  scenario_id: scenario,
  seats: [{ id: "human", name: "Аян", color: "#479e8b", bot: "", ready: true }],
  match: null,
  closed: false,
});
const rng = () => {
  let count = 0;
  return (n) => (count++ * 17 + 7) % n;
};
const canonical = (value) =>
  Array.isArray(value)
    ? `[${value.map(canonical).join(",")}]`
    : value && typeof value === "object"
      ? `{${Object.keys(value)
          .sort()
          .map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`)
          .join(",")}}`
      : JSON.stringify(value);
const digest = (room) =>
  createHash("sha256").update(canonical(room)).digest("hex");

test("браузер и сервер одинаково обрабатывают команды и повторную покупку", () => {
  let room = initial(catalog.scenarios[0].id);
  const random = rng();
  for (const item of contract.commands) {
    const result = applyCommand(catalog, room, "human", item.command, random);
    assert.equal(result.outcome, item.outcome);
    room = result.room;
    assert.equal(digest(room), item.hash);
  }
});
for (const game of contract.games)
  test(`полная партия ${game.scenario}: браузер совпадает с сервером`, () => {
    let room = initial(game.scenario);
    const random = rng();
    for (const bot of ["balanced", "builder"])
      room = applyCommand(
        catalog,
        room,
        "human",
        { revision: room.revision, kind: "add_bot", target: bot },
        random,
      ).room;
    room = applyCommand(
      catalog,
      room,
      "human",
      { revision: room.revision, kind: "start" },
      random,
    ).room;
    for (let i = 0; i < game.steps; i++) room = autoTurn(catalog, room, random);
    assert.equal(room.match.phase, "finished");
    assert.equal(digest(room), game.hash);
    assert.ok(room.match.players.every((p) => p.cash >= 0));
    assert.ok(
      netWorth(boardFor(catalog, room), room.match, room.match.winner) >= 0,
    );
  });
