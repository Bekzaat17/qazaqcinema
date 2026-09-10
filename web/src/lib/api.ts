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

/**
 * Сеть не ответила: обрыв, самолётный режим, ушли в лифт — либо наш таймаут.
 *
 * Отдельный класс, потому что лечится иначе, чем HTTP-ошибка: тут не «сервер сказал
 * нет», а «мы не знаем». Юзеру такое надо показывать кнопкой «Қайталау», а не текстом
 * «фильм не найден».
 */
export class NetworkError extends Error {
  constructor(readonly timedOut: boolean) {
    super(timedOut ? "network timeout" : "network unreachable");
    this.name = "NetworkError";
  }
}

/**
 * Сессию починить нечем: initData протух вместе с ней.
 *
 * Тупиковое состояние, которое НЕЛЬЗЯ проглатывать. Telegram не переписывает initData
 * у уже открытого Mini App, а TTL у него и у серверной сессии одинаковый (24 ч) —
 * значит у WebView, прожившего сутки (обычное дело на iOS), ре-auth упирается в тот же
 * просроченный initData. Без этого класса приложение оставалось бы в состоянии `ready`
 * с виду рабочим каталогом, где КАЖДОЕ нажатие даёт «қате шықты» и ничего больше.
 * Единственное лечение — переоткрыть Mini App, и сказать об этом должен экран.
 */
export class SessionExpiredError extends Error {
  constructor() {
    super("session expired");
    this.name = "SessionExpiredError";
  }
}

/**
 * Потолок ожидания одного запроса.
 *
 * ⚠️ Без него зависшее (не упавшее) соединение не реджектится НИКОГДА: `fetch` без
 * `signal` будет ждать столько, сколько живёт сокет. На мобильной сети это штатная
 * ситуация, и цена была высокой — экран навсегда оставался скелетом, а флаг «идёт
 * отправка видео» навсегда гасил кнопку «Көру» на всех фильмах сразу.
 *
 * 15 с: выдача видео просит бота отправить файл, и на медленном канале это законно
 * занимает несколько секунд; меньше — рвали бы живые запросы.
 */
const REQUEST_TIMEOUT_MS = 15_000;

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

  // Таймаут через AbortController: единственный способ заставить зависший fetch
  // реджектнуться (см. REQUEST_TIMEOUT_MS).
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        Authorization: opts?.auth ?? authHeader(),
        ...(init?.headers ?? {}),
      },
    });
  } catch (error) {
    // И обрыв сети, и наш abort приходят сюда. Различаем их только для диагностики:
    // лечение у обоих одно — предложить повторить.
    throw new NetworkError(controller.signal.aborted);
  } finally {
    clearTimeout(timer);
  }
  // Токен протух / Redis мигнул → сбрасываем сессию, чиним её и повторяем запрос ОДИН раз.
  // Ре-auth идёт по initData (stateless HMAC), поэтому переживает недоступность Redis.
  if (response.status === 401 && !opts?.retried) {
    // Токена нет — значит мы и так шли по initData, и сервер только что отверг именно
    // его. Чинить нечем: ре-auth пойдёт с тем же initData и получит тот же 401.
    if (!sessionToken) throw new SessionExpiredError();
    setSessionToken(null);
    // Если ре-auth сам упрётся в 401, он бросит `SessionExpiredError` строкой ниже
    // (его запрос идёт с `retried: true`) — и она пролетит наверх как есть.
    await refreshSession();
    return request<T>(path, init, { retried: true });
  }
  // Уже перезаходили по initData и снова 401 — дальше повторять некуда.
  if (response.status === 401) throw new SessionExpiredError();
  if (!response.ok) return readError(response);
  // 204 No Content (тумблер звезды) — тела нет, и `.json()` на пустом ответе бросил бы
  // SyntaxError. Такие ручки типизированы как void, поэтому отдаём undefined.
  if (response.status === 204) return undefined as T;
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
  notifications_enabled: boolean; // тумблер рассылок о новинках (Фаза 12)
  // Подарочный первый фильм. `free_view_available` — подарок ещё цел (показываем
  // приглашение вместо пэйволла); `free_view_movie_id` — какой фильм уже подарен
  // (на нём рисуем бейдж «Сыйлық» и не зовём платить).
  free_view_available: boolean;
  free_view_movie_id: number | null;
  // Открыт ли чат с ботом. Видео уходит ТОЛЬКО в личку, а написать первым бот не вправе —
  // зашедшему по ссылке (из браузера/поиска) «Көру» физически не сработает. false → зовём
  // в бота ДО того, как он потратит подарок, вместо ошибки после.
  bot_started: boolean;
}

export interface Movie {
  id: number;
  title_kk: string;
  title_ru: string | null;
  title_original: string | null;
  description: string;
  categories: string[]; // мультикатегории: фильм может относиться к нескольким
  poster_url: string;
  year: number | null;
  rating: number | null;
}

/** Полка главной: ключ (fresh/popular), казахская подпись, фильмы (собрано на бэке). */
export interface Shelf {
  key: string;
  title: string;
  movies: Movie[];
}

/** Агрегат главного экрана (Фаза 13): hero + готовые полки (ограничены на бэке). */
export interface CatalogHome {
  // Hero = фильм дня: то, что сегодня можно посмотреть бесплатно.
  hero: Movie | null;
  // До какого момента hero бесплатен (ISO, ближайшая местная полночь). Считает бэк —
  // отсчёт на экране обязан сходиться с тем, что реально пустит выдача видео.
  hero_free_until: string | null;
  shelves: Shelf[];
}

export type SortField = "year" | "rating" | "views";
export type SortDir = "asc" | "desc";

/** Страница каталога (Фаза 13): срез + метаданные пагинации. */
export interface MoviePage {
  items: Movie[];
  total: number;
  page: number;
  limit: number;
  has_more: boolean;
}

/** Непустая категория со счётчиком — для чипов-фильтра каталога. */
export interface CategoryCount {
  slug: string;
  count: number;
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
  kaspi_link: string | null;
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

  /** Свежий статус доступа (опрос, пока чек «на проверке»). Новую сессию НЕ заводит. */
  me: () => request<Auth>("/api/me"),

  /** Главный экран одним ответом (hero + готовые полки); кэшируется cache-aside (Фаза 11.2/13). */
  home: () => request<CatalogHome>("/api/movies/home"),

  /** Страница каталога: мультифильтр по категориям, сортировка, пагинация (Фаза 13). */
  browse: (categories: string[], sort: SortField, direction: SortDir, page: number, limit = 24) => {
    const params = new URLSearchParams({ sort, direction, page: String(page), limit: String(limit) });
    if (categories.length) params.set("categories", categories.join(","));
    return request<MoviePage>(`/api/movies?${params.toString()}`);
  },

  /** Непустые категории со счётчиками — для чипов-фильтра каталога (Фаза 13). */
  categories: () => request<CategoryCount[]>("/api/movies/categories"),

  searchMovies: (q: string) =>
    request<Movie[]>(`/api/movies/search?q=${encodeURIComponent(q)}`),

  getMovie: (id: number) => request<Movie>(`/api/movies/${id}`),

  /** Триггер защищённой выдачи: бот пришлёт видео в личку (protect_content). 403 → нет доступа.
   *
   * `useFreeView` — согласие потратить подарочный первый фильм. Без него сервер подарок
   * не тратит: иначе он сгорал бы от случайного перехода по ссылке на фильм.
   * `gift` в ответе — видео ушло именно за счёт подарка (фронт покажет это явно).
   */
  play: (id: number, useFreeView = false) =>
    request<{ status: "sent"; gift: boolean; daily: boolean }>(
      `/api/movies/${id}/play${useFreeView ? "?use_free_view=true" : ""}`,
      { method: "POST" },
    ),

  /** Избранное («Таңдаулы») текущего юзера — содержимое третьей вкладки. */
  favorites: () => request<Movie[]>("/api/favorites"),

  /** Только id избранного: ими фронт закрашивает звёзды в полках и каталоге.
   *
   * Отдельно от карточек фильма, потому что ответы каталога кэшируются одни на всех —
   * персональный флаг внутри них показал бы одному юзеру избранное другого.
   */
  favoriteIds: () => request<{ ids: number[] }>("/api/favorites/ids"),

  /** Поставить звезду (идемпотентно — повтор ничего не меняет). */
  addFavorite: (id: number) =>
    request<void>(`/api/favorites/${id}`, { method: "PUT" }),

  /** Снять звезду (тоже идемпотентно). */
  removeFavorite: (id: number) =>
    request<void>(`/api/favorites/${id}`, { method: "DELETE" }),

  /**
   * Человек разрешил боту писать в личку (нативный попап) — зафиксировать это на сервере.
   * Возвращает свежий Auth: `bot_started` в нём уже true, и «Көру» работает сразу.
   */
  grantWriteAccess: () => request<Auth>("/api/me/write-access", { method: "POST" }),

  /**
   * «Показали пэйволл» — единственный шаг воронки, о котором знает только фронт.
   * Шлётся фоном: ответ не нужен, ошибка гасится на вызывающей стороне.
   */
  trackPaywall: (movieId: number | null) =>
    request<void>("/api/events/paywall", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ movie_id: movieId }),
    }),

  /**
   * Спрос словами: запрос, на котором человек ОСТАНОВИЛСЯ, и сколько по нему нашлось.
   *
   * Шлёт именно фронт, а не серверный `/api/movies/search`: поиск дебаунсится на 300 мс,
   * и сервер видит префиксы недонабранного слова («кун», «кунг ф»). На чём человек
   * остановился, знает только клиент — по паузе в наборе (см. SEARCH_TRACK_MS в App.tsx).
   * Фоном: ответ не нужен, ошибка гасится на вызывающей стороне.
   */
  trackSearch: (query: string, found: number) =>
    request<void>("/api/events/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, found }),
    }),

  /**
   * Уход в чат за видео: `try` — нажали кнопку, `stuck` — секунда прошла, а мы всё ещё
   * на экране. Только фронт знает, послушался ли нативный клиент Telegram; из этих двух
   * счётчиков по платформам и складывается доля сломанных уходов. Шлём фоном.
   */
  trackHandoff: (outcome: "try" | "stuck", platform: string) =>
    request<void>("/api/events/handoff", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ outcome, platform }),
    }),

  /** Тумблер рассылок о новинках (Фаза 12): включить/выключить для текущего юзера. */
  setNotifications: (enabled: boolean) =>
    request<{ notifications_enabled: boolean }>("/api/me/notifications", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    }),

  /** Написать админам/техподдержке из Mini App: сообщение уходит им в личку Telegram. */
  sendSupport: (text: string) =>
    request<{ status: string }>("/api/support", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    }),

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
