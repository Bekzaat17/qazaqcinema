// Клиент бэкенда. initData уходит в заголовке Authorization (валидируется на бэке HMAC).
// Пустой BASE_URL → тот же origin (в dev это Vite-прокси на localhost:8000, см. vite.config).

import { getInitData } from "./telegram";

const BASE_URL = import.meta.env.VITE_API_URL ?? "";

// ── Серверная сессия (Фаза 11.1) ──
// initData — bootstrap (HMAC один раз). Дальше ходим с непрозрачным токеном из Redis,
// хранимым в localStorage. На 401 (протух / Redis мигнул) — прозрачный ре-auth по initData.
const SESSION_KEY = "qc_session";
let sessionToken: string | null = localStorage.getItem(SESSION_KEY);

interface RequestOpts {
  auth?: string; // явный заголовок (bootstrap /api/auth всегда шлёт initData)
  retried?: boolean; // защита от бесконечного цикла ре-auth
}

function setSessionToken(token: string | null): void {
  sessionToken = token;
  if (token) localStorage.setItem(SESSION_KEY, token);
  else localStorage.removeItem(SESSION_KEY);
}

/** Authorization: серверный токен (после bootstrap) либо initData (bootstrap/фолбэк). */
function authHeader(): string {
  return sessionToken ?? getInitData();
}

/** Ошибка API с HTTP-статусом и машинным кодом (`detail`) — чтобы ветвить на 403 no_access и т.п. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
  ) {
    super(`API ${status}: ${code}`);
    this.name = "ApiError";
  }
}

async function readError(response: Response): Promise<never> {
  let code = response.statusText || "error";
  try {
    const body = (await response.json()) as { detail?: string };
    if (typeof body.detail === "string") code = body.detail;
  } catch {
    /* тело не JSON — оставляем статус-текст */
  }
  throw new ApiError(response.status, code);
}

async function request<T>(path: string, init?: RequestInit, opts?: RequestOpts): Promise<T> {
  // DEV вне Telegram (нет initData) → мок бэкенда, чтобы отлаживать вёрстку в браузере.
  // В прод-сборке import.meta.env.DEV === false → ветка мертва, devMock не бандлится.
  if (import.meta.env.DEV && !getInitData()) {
    const { mockJson } = await import("./devMock");
    return mockJson<T>(path, init);
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      Authorization: opts?.auth ?? authHeader(),
      ...(init?.headers ?? {}),
    },
  });
  // Токен протух / Redis мигнул → сбрасываем сессию, чиним её и повторяем запрос ОДИН раз.
  // Ре-auth идёт по initData (stateless HMAC), поэтому переживает недоступность Redis.
  if (response.status === 401 && sessionToken && !opts?.retried) {
    setSessionToken(null);
    await refreshSession();
    return request<T>(path, init, { retried: true });
  }
  if (!response.ok) return readError(response);
  return (await response.json()) as T;
}

let refreshing: Promise<Auth> | null = null;

/** Bootstrap/ре-auth по initData: сервер заводит сессию, сохраняем токен (null при Redis-дауне). */
function refreshSession(): Promise<Auth> {
  // dedupe: параллельные 401 не должны стрелять несколькими /api/auth. retried:true —
  // сам bootstrap повторять некуда (иначе рекурсия ре-auth на собственный 401).
  refreshing ??= request<Auth>("/api/auth", { method: "POST" }, { auth: getInitData(), retried: true })
    .then((auth) => {
      setSessionToken(auth.token ?? null);
      return auth;
    })
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

// ── DTO (зеркала pydantic-схем бэкенда) ──
export type UserStatus = "new" | "pending_review" | "active" | "expired";

export interface Auth {
  telegram_id: number;
  status: UserStatus;
  expires_at: string | null;
  has_access: boolean;
  token?: string | null; // серверная сессия (Фаза 11.1); null → остаёмся на initData
}

export interface Movie {
  id: number;
  title_kk: string;
  title_ru: string | null;
  title_original: string | null;
  description: string;
  category: string;
  poster_url: string;
  year: number | null;
  rating: number | null;
  hero_image_url?: string | null; // горизонтальный баннер, если фильм показан на hero
}

/** Агрегат главного экрана (Фаза 11.2): hero + все фильмы одним ответом. */
export interface CatalogHome {
  hero: Movie | null;
  movies: Movie[];
}

export interface Tariff {
  slug: string;
  title_ru: string;
  title_kk: string;
  price_kzt: number;
  price_xtr: number;
  days: number;
  recurring: boolean;
}

export type PaymentMethod = "kaspi" | "stars";

export interface PaymentInit {
  method: string;
  kaspi_number: string | null;
  kaspi_name: string | null;
  invoice_url: string | null;
  payload: string | null;
}

export interface ProofAccepted {
  status: string;
  request_id: number;
}

export const api = {
  /** Bootstrap/ре-auth: initData → сессия. Токен кладётся в localStorage автоматически. */
  auth: () => refreshSession(),

  /** Главный экран одним ответом (hero + фильмы); кэшируется на бэке cache-aside (Фаза 11.2). */
  home: () => request<CatalogHome>("/api/movies/home"),

  movies: (category?: string) =>
    request<Movie[]>(`/api/movies${category ? `?category=${encodeURIComponent(category)}` : ""}`),

  searchMovies: (q: string) =>
    request<Movie[]>(`/api/movies/search?q=${encodeURIComponent(q)}`),

  getMovie: (id: number) => request<Movie>(`/api/movies/${id}`),

  /** Фильм для hero главной — выбор делает бэкенд (featured → новизна). null, если каталог пуст. */
  hero: () => request<Movie | null>("/api/movies/hero"),

  /** Триггер защищённой выдачи: бот пришлёт видео в личку (protect_content). 403 → нет доступа. */
  play: (id: number) =>
    request<{ status: "sent" }>(`/api/movies/${id}/play`, { method: "POST" }),

  tariffs: () => request<Tariff[]>("/api/payments/tariffs"),

  initiatePayment: (tariff: string, method: PaymentMethod) =>
    request<PaymentInit>("/api/payments/initiate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tariff, method }),
    }),

  submitProof: (tariff: string, file: File) => {
    const form = new FormData();
    form.append("tariff", tariff);
    form.append("file", file);
    return request<ProofAccepted>("/api/payments/proof", { method: "POST", body: form });
  },
};
