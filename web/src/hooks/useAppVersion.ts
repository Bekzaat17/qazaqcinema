// Определение «вышла новая версия приложения».
//
// Зачем: Mini App живёт в WebView, который держит страницу открытой сутками. После
// деплоя человек продолжал видеть старый интерфейс, пока сам не догадается перезайти —
// разработчик догадается, обычный пользователь нет.
//
// Как: сравниваем имя бандла, с которым мы ЗАПУСТИЛИСЬ, с тем, на который ссылается
// свежий index.html на сервере. Vite кладёт в имя хеш содержимого (index-D7ZNyEhZ.js),
// поэтому несовпадение имён — это ровно «сборка другая», без версий и счётчиков.
// Отдельный /version.json для этого не нужен: index.html и так всегда свежий (Caddy
// отдаёт его с Cache-Control: no-cache).
//
// Сам по себе хук НИЧЕГО не перезагружает — только поднимает флаг. Когда именно
// применять обновление, решает App: посреди оплаты дёргать reload нельзя.

import { useCallback, useEffect, useRef, useState } from "react";

/** Как часто проверять в фоне. Редко: основной триггер — возврат в приложение. */
const CHECK_INTERVAL_MS = 10 * 60 * 1000;

const BUNDLE_RE = /assets\/index-[A-Za-z0-9_-]+\.js/;

/** Имя бандла, с которым работает ТЕКУЩАЯ страница (из её же <script type="module">). */
function currentBundle(): string | null {
  const script = document.querySelector<HTMLScriptElement>('script[type="module"][src]');
  return script?.src.match(BUNDLE_RE)?.[0] ?? null;
}

/** Имя бандла в свежем index.html с сервера. null — не достучались или формат другой. */
async function deployedBundle(): Promise<string | null> {
  try {
    const response = await fetch(`/index.html?_=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.text()).match(BUNDLE_RE)?.[0] ?? null;
  } catch {
    return null; // сеть моргнула — проверим в следующий раз
  }
}

/**
 * `true`, когда на сервере лежит сборка новее запущенной.
 *
 * Флаг взводится один раз и не гаснет: обновление никуда не денется, а мигающий флаг
 * заставил бы вызывающего гадать.
 */
export function useAppVersion(): boolean {
  const [updateReady, setUpdateReady] = useState(false);
  // Считаем один раз при монтировании: DOM может измениться, а запущенная версия — нет.
  const bundleRef = useRef<string | null>(currentBundle());

  const check = useCallback(async () => {
    // В DEV бандла с хешем нет (Vite отдаёт модули по одному) — сравнивать нечего.
    if (import.meta.env.DEV || bundleRef.current === null || updateReady) return;
    const deployed = await deployedBundle();
    // Только явное несовпадение. При null (сеть, прокси, другой формат) молчим:
    // ложное срабатывание здесь означает перезагрузку страницы на ровном месте.
    if (deployed !== null && deployed !== bundleRef.current) setUpdateReady(true);
  }, [updateReady]);

  useEffect(() => {
    void check();
    const timer = setInterval(() => {
      if (!document.hidden) void check();
    }, CHECK_INTERVAL_MS);
    const onResume = () => {
      if (!document.hidden) void check();
    };
    document.addEventListener("visibilitychange", onResume);
    window.addEventListener("focus", onResume);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onResume);
      window.removeEventListener("focus", onResume);
    };
  }, [check]);

  return updateReady;
}
