// DEV-ONLY мок бэкенда. Позволяет открыть Mini App в обычном браузере (без Telegram initData
// и без запущенного API) для отладки вёрстки. В прод-сборку НЕ попадает: вызывается только из
// ветки `import.meta.env.DEV && !initData` через динамический import (Vite вырезает её в проде).

import type {
  Auth,
  CatalogHome,
  CategoryCount,
  Movie,
  MoviePage,
  PaymentInit,
  ProofAccepted,
  Shelf,
  Tariff,
} from "./api";

const poster = (seed: string) => `https://picsum.photos/seed/${seed}/400/600`;

const MOVIES: Movie[] = [
  { id: 7, title_kk: "Аспандағы құлып", title_ru: "Ходячий замок", title_original: "Howl's Moving Castle", description: "Жас қалпақшы қыз сиқыршының қарғысына ұшырап, жүретін құлыптан пана табады.", categories: ["anime", "fantasy"], poster_url: poster("howl"), year: 2004, rating: 8.9 },
  { id: 6, title_kk: "Арыстан патша", title_ru: "Король Лев", title_original: "The Lion King", description: "Жас арыстан Симбаның патшалыққа жол тартқан тағдыры.", categories: ["disney", "family"], poster_url: poster("lion"), year: 1994, rating: 8.5 },
  { id: 5, title_kk: "Мұзды өлке", title_ru: "Холодное сердце", title_original: "Frozen", description: "Екі әпкенің махаббаты мен сиқыры туралы жылы ертегі.", categories: ["disney", "fantasy", "girls"], poster_url: poster("frozen"), year: 2013, rating: 7.4 },
  { id: 4, title_kk: "Рухтардың әлемі", title_ru: "Унесённые призраками", title_original: "Spirited Away", description: "Тихиро аруақтар мекеніне тап болып, ата-анасын құтқаруға тырысады.", categories: ["anime", "fantasy"], poster_url: poster("spirited"), year: 2001, rating: 8.6 },
  { id: 3, title_kk: "ВАЛЛ·И", title_ru: "ВАЛЛ·И", title_original: "WALL·E", description: "Жалғыз робот тастанды Жерде махаббат пен үміт іздейді.", categories: ["disney"], poster_url: poster("walle"), year: 2008, rating: 8.4 },
  { id: 2, title_kk: "Тоторо", title_ru: "Мой сосед Тоторо", title_original: "My Neighbor Totoro", description: "Апалы-сіңлілі қыздар орман рухы Тоторомен достасады.", categories: ["anime", "kids"], poster_url: poster("totoro"), year: 1988, rating: 8.2 },
  { id: 1, title_kk: "Батыл жүрек", title_ru: "Храбрая сердцем", title_original: "Brave", description: "Мерида ханшайым өз тағдырын өзі шешуге бел буады.", categories: ["disney", "adventure"], poster_url: poster("brave"), year: 2012, rating: 7.1 },
];

// Фильм на hero: у него есть горизонтальный баннер 3:2 (проверить широкий hero в браузере).
const HERO_MOVIE: Movie = { ...MOVIES[0], hero_image_url: "https://picsum.photos/seed/howl-hero/1200/800" };

// Полки главной (как их собрал бы бэкенд): «Жаңа түскен» без hero + «Танымал» (по рейтингу-прокси).
const SHELVES: Shelf[] = [
  { key: "fresh", title: "Жаңа түскен", movies: MOVIES.filter((m) => m.id !== HERO_MOVIE.id) },
  { key: "popular", title: "Танымал", movies: [...MOVIES].sort((a, b) => (b.rating ?? 0) - (a.rating ?? 0)) },
];
const HOME: CatalogHome = { hero: HERO_MOVIE, shelves: SHELVES };

const TARIFFS: Tariff[] = [
  { slug: "1_day", title_ru: "1 день", title_kk: "1 күн", price_kzt: 290, price_xtr: 50, days: 1, recurring: false },
  { slug: "1_month", title_ru: "1 месяц", title_kk: "1 ай", price_kzt: 1290, price_xtr: 200, days: 30, recurring: true },
];

// Реквизиты Kaspi для мок-превью берём из Vite-env (web/.env.local), чтобы форма оплаты
// в браузере показывала те же значения, что реальный бэкенд из своего .env (PAY_KASPI_*).
// Пустой VITE_PAY_KASPI_LINK → способ «оплата по ссылке» скрыт — как `X or None` на бэке.
const KASPI_NUMBER: string = import.meta.env.VITE_PAY_KASPI_NUMBER || "+7 700 123 4567";
const KASPI_NAME: string = import.meta.env.VITE_PAY_KASPI_NAME || "QazaqCinema";
const KASPI_LINK: string | null = import.meta.env.VITE_PAY_KASPI_LINK || null;

// Поменяй status на "active"/"new"/"pending_review", чтобы посмотреть разные состояния UI в браузере.
const AUTH: Auth = {
  telegram_id: 1,
  status: "active",
  expires_at: new Date(Date.now() + 20 * 86_400_000).toISOString(),
  has_access: true,
  token: null, // в dev-моке токен-флоу не задействован (request() уходит в мок до fetch)
  notifications_enabled: true, // тумблер рассылок (Фаза 12)
};

/** Непустые категории со счётчиками (для чипов каталога). */
function categoryCounts(): CategoryCount[] {
  const counts = new Map<string, number>();
  for (const m of MOVIES) for (const c of m.categories) counts.set(c, (counts.get(c) ?? 0) + 1);
  return [...counts.entries()].map(([slug, count]) => ({ slug, count }));
}

/** Пагинированный браузинг: фильтр по категориям + сортировка + срез (мок бэкенда Фазы 13). */
function browse(q: URLSearchParams): MoviePage {
  const cats = (q.get("categories") ?? "").split(",").filter(Boolean);
  const sort = q.get("sort") ?? "year";
  const dir = q.get("direction") ?? "desc";
  const page = Number(q.get("page") ?? "1");
  const limit = Number(q.get("limit") ?? "24");

  const list = cats.length ? MOVIES.filter((m) => m.categories.some((c) => cats.includes(c))) : [...MOVIES];
  // views нет в моке → id; year → год выпуска (без года — в конец)
  const key = (m: Movie): number => (sort === "rating" ? (m.rating ?? -1) : sort === "year" ? (m.year ?? -1) : m.id);
  list.sort((a, b) => (dir === "asc" ? key(a) - key(b) : key(b) - key(a)));

  const start = (page - 1) * limit;
  const items = list.slice(start, start + limit);
  return { items, total: list.length, page, limit, has_more: start + items.length < list.length };
}

export function mockJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = new URL(path, "http://mock");
  const p = url.pathname;
  const q = url.searchParams;

  let data: unknown;
  if (p === "/api/auth") data = AUTH;
  else if (p === "/api/movies/home") data = HOME;
  else if (p === "/api/movies/categories") data = categoryCounts();
  else if (p === "/api/movies/search") {
    const term = (q.get("q") ?? "").toLowerCase();
    data = MOVIES.filter((m) => `${m.title_kk} ${m.title_original}`.toLowerCase().includes(term));
  } else if (p === "/api/movies") data = browse(q);
  else if (/^\/api\/movies\/\d+\/play$/.test(p)) data = { status: "sent" };
  else if (/^\/api\/movies\/\d+$/.test(p)) data = MOVIES.find((m) => m.id === Number(p.split("/")[3]));
  else if (p === "/api/payments/tariffs") data = TARIFFS;
  else if (p === "/api/payments/initiate") {
    const method = init?.body ? (JSON.parse(String(init.body)) as { method: string }).method : "kaspi";
    data =
      method === "stars"
        ? ({ method: "stars", kaspi_number: null, kaspi_name: null, kaspi_link: null, invoice_url: "https://t.me/invoice/mock", payload: "1:1_month" } satisfies PaymentInit)
        : ({ method: "kaspi", kaspi_number: KASPI_NUMBER, kaspi_name: KASPI_NAME, kaspi_link: KASPI_LINK, invoice_url: null, payload: null } satisfies PaymentInit);
  } else if (p === "/api/payments/proof") data = { status: "pending_review", request_id: 1 } satisfies ProofAccepted;
  else if (p === "/api/me/notifications") {
    const enabled = init?.body ? (JSON.parse(String(init.body)) as { enabled: boolean }).enabled : true;
    data = { notifications_enabled: enabled };
  }

  return new Promise((resolve) => setTimeout(() => resolve(data as T), 350));
}
