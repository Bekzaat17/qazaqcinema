import assert from "node:assert/strict";
import test from "node:test";
import {
  clearPaymentReturn,
  loadPaymentReturn,
  PAYMENT_RETURN_TTL_MS,
  savePaymentReturn,
} from "../src/lib/paymentReturn.ts";

const NOW = 1_795_685_000_000;

function mockStorage(t) {
  const entries = new Map();
  t.mock.method(Date, "now", () => NOW);
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: {
      setItem: (key, value) => entries.set(key, value),
      getItem: (key) => entries.get(key) ?? null,
      removeItem: (key) => entries.delete(key),
    },
  });
  t.after(() => delete globalThis.localStorage);
  return entries;
}

test("после перезапуска сохраняется выбранный фильм или профиль своего аккаунта", (t) => {
  mockStorage(t);
  savePaymentReturn(31, { movieId: 42 });
  savePaymentReturn(32, { movieId: null });
  assert.deepEqual(loadPaymentReturn(31), { movieId: 42 });
  assert.deepEqual(loadPaymentReturn(32), { movieId: null });
  assert.equal(loadPaymentReturn(33), null);
  clearPaymentReturn(31);
  assert.equal(loadPaymentReturn(31), null);
  assert.deepEqual(loadPaymentReturn(32), { movieId: null });
});

test("испорченная запись или старая оплата не открывает карточку", (t) => {
  const entries = mockStorage(t);
  savePaymentReturn(31, { movieId: 42 });
  const [key] = entries.keys();
  entries.set(key, JSON.stringify({ movieId: 42, savedAt: NOW - PAYMENT_RETURN_TTL_MS - 1 }));
  assert.equal(loadPaymentReturn(31), null);
  entries.set(key, JSON.stringify({ movieId: "42", savedAt: NOW }));
  assert.equal(loadPaymentReturn(31), null);
  entries.set(key, "{");
  assert.equal(loadPaymentReturn(31), null);
});

test("оплата продолжает работать при недоступном локальном хранилище", () => {
  assert.doesNotThrow(() => savePaymentReturn(31, { movieId: 42 }));
  assert.equal(loadPaymentReturn(31), null);
  assert.doesNotThrow(() => clearPaymentReturn(31));
});
