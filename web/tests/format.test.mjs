import assert from "node:assert/strict";
import test from "node:test";
import { COIN_SYMBOL, gameText, money, moneyLabel, roundLimitLabel } from "../src/boardgame/format.ts";

test("режим без лимита не показывается как ноль кругов", () => {
  assert.equal(roundLimitLabel(0), "Шектеусіз");
  assert.equal(roundLimitLabel(12), "12 айналым");
});

test("цены партии используют игровую монету, а доступная подпись называет её", () => {
  assert.equal(money(1200), `${(1200).toLocaleString("kk-KZ")} ${COIN_SYMBOL}`);
  assert.equal(money(0), `0 ${COIN_SYMBOL}`);
  assert.match(moneyLabel(1200), /Dala ойын монетасы$/);
  assert.doesNotMatch(money(1200), /₸|теңге/);
});

test("старые и серверные журналы показывают новую монету без изменения сумм", () => {
  const oldLine = "Жалдау ақысы: 240 ₸ → Айбар";
  assert.equal(gameText(oldLine), "Жалдау ақысы: 240 ◈ → Айбар");
  assert.equal(gameText("Айналым: +160 ₸; алым: 50 ₸"), "Айналым: +160 ◈; алым: 50 ◈");
  assert.equal(gameText("Ойын теңгесі жеткіліксіз."), "Ойын монетасы жеткіліксіз.");
  assert.equal(gameText(gameText(oldLine)), gameText(oldLine));
  assert.equal(gameText("Кезек Айбарға өтті"), "Кезек Айбарға өтті");
});
