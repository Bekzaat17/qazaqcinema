// Где юзер был в прошлый раз (вкладка + открытая карточка фильма).
//
// Mini App живёт короткими заходами: свернул Telegram, ушёл в чат с ботом за видео,
// вернулся — и раньше каждый раз начинал с главной, заново долистывая до нужного места.
// Запоминаем последний экран и восстанавливаем его, если возврат случился в течение TTL.
// Дальше это уже не «продолжить», а «навязать старое» — открываем главную.
//
// Хранилище — localStorage (переживает закрытие Mini App, в отличие от состояния React).
// Все обращения в try/catch: в приватном режиме браузера доступ к нему кидает исключение,
// а из-за памяти о вкладке приложение падать не должно.

export const LAST_PAGE_TTL_MS = 60 * 60 * 1000; // 60 минут

const KEY = "qc_last_page";

export type LastTab = "home" | "catalog" | "favorites";

export interface LastPage {
  tab: LastTab;
  movieId: number | null; // открытая карточка фильма; null — просто вкладка
}

interface StoredPage extends LastPage {
  ts: number;
}

export function saveLastPage(page: LastPage): void {
  try {
    const stored: StoredPage = { ...page, ts: Date.now() };
    localStorage.setItem(KEY, JSON.stringify(stored));
  } catch {
    /* приватный режим / переполнение — память о вкладке не стоит падения */
  }
}

/** Последний экран, если он ещё «свежий». Протух, битый или его нет → null. */
export function loadLastPage(): LastPage | null {
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(KEY);
  } catch {
    return null;
  }
  if (!raw) return null;
  try {
    const stored = JSON.parse(raw) as Partial<StoredPage>;
    if (typeof stored.ts !== "number" || Date.now() - stored.ts > LAST_PAGE_TTL_MS) return null;
    // Белый список, а не приведение типа: в ключе может лежать что угодно (старый формат,
    // чужая запись), и «home» — безопасный фолбэк для любого неизвестного значения.
    const known: LastTab[] = ["home", "catalog", "favorites"];
    const tab: LastTab = known.find((t) => t === stored.tab) ?? "home";
    const movieId = typeof stored.movieId === "number" ? stored.movieId : null;
    return { tab, movieId };
  } catch {
    return null; // мусор в ключе (старый формат) — просто начинаем с главной
  }
}
