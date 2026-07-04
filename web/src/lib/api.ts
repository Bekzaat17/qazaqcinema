// Клиент бэкенда. initData уходит в заголовке Authorization (валидируется на бэке HMAC).
// Пустой BASE_URL → тот же origin (в dev это Vite-прокси на localhost:8000, см. vite.config).

import { getInitData } from "./telegram";

const BASE_URL = import.meta.env.VITE_API_URL ?? "";

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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // DEV вне Telegram (нет initData) → мок бэкенда, чтобы отлаживать вёрстку в браузере.
  // В прод-сборке import.meta.env.DEV === false → ветка мертва, devMock не бандлится.
  if (import.meta.env.DEV && !getInitData()) {
    const { mockJson } = await import("./devMock");
    return mockJson<T>(path, init);
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      Authorization: getInitData(),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) return readError(response);
  return (await response.json()) as T;
}

// ── DTO (зеркала pydantic-схем бэкенда) ──
export type UserStatus = "new" | "pending_review" | "active" | "expired";

export interface Auth {
  telegram_id: number;
  status: UserStatus;
  expires_at: string | null;
  has_access: boolean;
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
  auth: () => request<Auth>("/api/auth", { method: "POST" }),

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
