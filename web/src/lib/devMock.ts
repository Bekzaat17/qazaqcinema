// DEV-ONLY мок бэкенда. Позволяет открыть Mini App в обычном браузере (без Telegram initData
// и без запущенного API) для отладки вёрстки. В прод-сборку НЕ попадает: вызывается только из
// ветки `import.meta.env.DEV && !initData` через динамический import (Vite вырезает её в проде).

import type { Auth, CatalogHome, Movie, PaymentInit, ProofAccepted, Tariff } from "./api";

const poster = (seed: string) => `https://picsum.photos/seed/${seed}/400/600`;

const MOVIES: Movie[] = [
  { id: 7, title_kk: "Аспандағы құлып", title_ru: "Ходячий замок", title_original: "Howl's Moving Castle", description: "Жас қалпақшы қыз сиқыршының қарғысына ұшырап, жүретін құлыптан пана табады.", category: "anime", poster_url: poster("howl"), year: 2004, rating: 8.9 },
  { id: 6, title_kk: "Арыстан патша", title_ru: "Король Лев", title_original: "The Lion King", description: "Жас арыстан Симбаның патшалыққа жол тартқан тағдыры.", category: "disney", poster_url: poster("lion"), year: 1994, rating: 8.5 },
  { id: 5, title_kk: "Мұзды өлке", title_ru: "Холодное сердце", title_original: "Frozen", description: "Екі әпкенің махаббаты мен сиқыры туралы жылы ертегі.", category: "disney", poster_url: poster("frozen"), year: 2013, rating: 7.4 },
  { id: 4, title_kk: "Рухтардың әлемі", title_ru: "Унесённые призраками", title_original: "Spirited Away", description: "Тихиро аруақтар мекеніне тап болып, ата-анасын құтқаруға тырысады.", category: "anime", poster_url: poster("spirited"), year: 2001, rating: 8.6 },
  { id: 3, title_kk: "ВАЛЛ·И", title_ru: "ВАЛЛ·И", title_original: "WALL·E", description: "Жалғыз робот тастанды Жерде махаббат пен үміт іздейді.", category: "disney", poster_url: poster("walle"), year: 2008, rating: 8.4 },
  { id: 2, title_kk: "Тоторо", title_ru: "Мой сосед Тоторо", title_original: "My Neighbor Totoro", description: "Апалы-сіңлілі қыздар орман рухы Тоторомен достасады.", category: "anime", poster_url: poster("totoro"), year: 1988, rating: 8.2 },
  { id: 1, title_kk: "Батыл жүрек", title_ru: "Храбрая сердцем", title_original: "Brave", description: "Мерида ханшайым өз тағдырын өзі шешуге бел буады.", category: "disney", poster_url: poster("brave"), year: 2012, rating: 7.1 },
];

// Фильм на hero: у первого мока есть горизонтальный баннер 3:2 (проверить широкий hero в браузере).
const HERO_MOVIE: Movie = { ...MOVIES[0], hero_image_url: "https://picsum.photos/seed/howl-hero/1200/800" };

const TARIFFS: Tariff[] = [
  { slug: "1_day", title_ru: "1 день", title_kk: "1 күн", price_kzt: 349, price_xtr: 50, days: 1, recurring: false },
  { slug: "1_month", title_ru: "1 месяц", title_kk: "1 ай", price_kzt: 1899, price_xtr: 250, days: 30, recurring: true },
];

// Поменяй status на "active"/"new"/"pending_review", чтобы посмотреть разные состояния UI в браузере.
const AUTH: Auth = {
  telegram_id: 1,
  status: "active",
  expires_at: new Date(Date.now() + 20 * 86_400_000).toISOString(),
  has_access: true,
  token: null, // в dev-моке токен-флоу не задействован (request() уходит в мок до fetch)
};

export function mockJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = new URL(path, "http://mock");
  const p = url.pathname;
  const q = url.searchParams;

  let data: unknown;
  if (p === "/api/auth") data = AUTH;
  else if (p === "/api/movies/home") data = { hero: HERO_MOVIE, movies: MOVIES } satisfies CatalogHome;
  else if (p === "/api/movies/hero") data = HERO_MOVIE;
  else if (p === "/api/movies/search") {
    const term = (q.get("q") ?? "").toLowerCase();
    data = MOVIES.filter((m) => `${m.title_kk} ${m.title_original}`.toLowerCase().includes(term));
  } else if (p === "/api/movies") {
    const cat = q.get("category");
    data = cat ? MOVIES.filter((m) => m.category === cat) : MOVIES;
  } else if (/^\/api\/movies\/\d+\/play$/.test(p)) data = { status: "sent" };
  else if (/^\/api\/movies\/\d+$/.test(p)) data = MOVIES.find((m) => m.id === Number(p.split("/")[3]));
  else if (p === "/api/payments/tariffs") data = TARIFFS;
  else if (p === "/api/payments/initiate") {
    const method = init?.body ? (JSON.parse(String(init.body)) as { method: string }).method : "kaspi";
    data =
      method === "stars"
        ? ({ method: "stars", kaspi_number: null, kaspi_name: null, invoice_url: "https://t.me/invoice/mock", payload: "1:1_month" } satisfies PaymentInit)
        : ({ method: "kaspi", kaspi_number: "+7 700 123 4567", kaspi_name: "QazaqCinema", invoice_url: null, payload: null } satisfies PaymentInit);
  } else if (p === "/api/payments/proof") data = { status: "pending_review", request_id: 1 } satisfies ProofAccepted;

  return new Promise((resolve) => setTimeout(() => resolve(data as T), 350));
}
