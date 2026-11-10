import assert from "node:assert/strict";
import test from "node:test";
import { fetchWithTimeout, FetchTimeoutError } from "../src/lib/transport.ts";

const hangingFetch = (_url, init) =>
  new Promise((_resolve, reject) => {
    init.signal.addEventListener("abort", () => reject(init.signal.reason), {
      once: true,
    });
  });

test("long-poll не обрывается раньше собственного срока ожидания", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  let settled = false;
  t.mock.method(
    globalThis,
    "fetch",
    (_url, init) =>
      new Promise((resolve, reject) => {
        const timer = setTimeout(() => resolve(new Response("{}")), 25000);
        init.signal.addEventListener(
          "abort",
          () => {
            clearTimeout(timer);
            reject(init.signal.reason);
          },
          { once: true },
        );
      }),
  );
  const pending = fetchWithTimeout("http://test", {}, 35000).then((r) => {
    settled = true;
    return r;
  });
  t.mock.timers.tick(15000);
  await Promise.resolve();
  assert.equal(settled, false);
  t.mock.timers.tick(10000);
  assert.equal((await pending).status, 200);
});

test("зависший запрос завершается своим таймаутом", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  t.mock.method(globalThis, "fetch", hangingFetch);
  const pending = assert.rejects(
    fetchWithTimeout("http://test", {}, 15000),
    FetchTimeoutError,
  );
  t.mock.timers.tick(15000);
  await pending;
});

test("выход из комнаты немедленно отменяет ожидающий запрос", async (t) => {
  t.mock.method(globalThis, "fetch", hangingFetch);
  const controller = new AbortController();
  const pending = fetchWithTimeout(
    "http://test",
    { signal: controller.signal },
    35000,
  );
  controller.abort();
  await assert.rejects(pending, { name: "AbortError" });
});

test("уже отменённый экран не отправляет новый запрос", async (t) => {
  const fetch = t.mock.method(globalThis, "fetch", hangingFetch);
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(
    fetchWithTimeout("http://test", { signal: controller.signal }, 35000),
    { name: "AbortError" },
  );
  assert.equal(fetch.mock.callCount(), 0);
});
