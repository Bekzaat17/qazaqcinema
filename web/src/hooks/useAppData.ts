// Данные приложения: авторизация, витрина, тарифы — и их свежесть.
//
// Здесь всё, что происходит «само»: загрузка на входе, вход по deep-link, возврат на
// прошлый экран, опрос статуса подписки и перезапрос каталога после сворачивания. Экран
// (App) получает готовое состояние и решает, что рисовать, а не как это добыть.

import { useCallback, useEffect, useRef, useState } from "react";

import type { LastTab } from "../lib/lastPage";
import {
  ApiError,
  SessionExpiredError,
  api,
  type Auth,
  type Movie,
  type Shelf as ShelfData,
  type Tariff,
  type UserStatus,
} from "../lib/api";
import { loadLastPage } from "../lib/lastPage";
import { getInitData, getStartMovieId, haptic } from "../lib/telegram";

// Как часто переспрашивать статус, пока чек «на проверке». Решение админа (✅/❌) приходит
// извне приложения, поэтому фронт узнаёт о нём только опросом. 20 с — незаметно для юзера
// и всего 3 запроса в минуту (лимит `/api/me` — 120/мин на IP, см. api/routers/me.py).
const STATUS_POLL_MS = 20_000;

// Не чаще этого перезапрашиваем каталог при возврате в приложение. Полминуты хватает,
// чтобы новинка, добавленная админом, появилась сама, и при этом «свернул-развернул»
// десять раз подряд не превращается в десять запросов.
const CONTENT_REFRESH_MS = 30_000;

/** Фаза экрана. `session_expired` — отдельная, потому что лечится не «повторить», а
 *  переоткрытием Mini App. */
export type Phase = "loading" | "ready" | "error" | "no_telegram" | "session_expired";

/**
 * Авторизация с одной повторной попыткой. `null` — не доехала (сеть).
 *
 * `SessionExpiredError` наружу пропускаем специально: её повторять бессмысленно (тот же
 * просроченный initData даст тот же ответ), и обработать её обязан вызывающий — своим
 * экраном, а не тихим `null`.
 */
async function retryAuth(): Promise<Auth | null> {
  try {
    return await api.auth();
  } catch (e) {
    if (e instanceof SessionExpiredError) throw e;
    try {
      return await api.auth();
    } catch (retryError) {
      if (retryError instanceof SessionExpiredError) throw retryError;
      return null;
    }
  }
}

export interface AppDataHandlers {
  /** Открыть карточку фильма (deep-link или восстановленный экран). */
  onOpenMovie: (movie: Movie) => void;
  /** Вернуть вкладку, на которой человека прервали. */
  onRestoreTab: (tab: LastTab) => void;
  /** Сказать человеку то, о чём он иначе не узнает (решение по чеку, битая ссылка). */
  onToast: (text: string) => void;
}

export interface AppData {
  phase: Phase;
  auth: Auth | null;
  setAuth: React.Dispatch<React.SetStateAction<Auth | null>>;
  status: UserStatus;
  shelves: ShelfData[];
  tariffs: Tariff[];
  hero: Movie | null;
  /** До какого момента hero (он же фильм дня) бесплатен. `null` → каталог пуст либо бэк
   *  старой версии: hero тогда обычная витрина, без бейджа и таймера. */
  heroFreeUntil: string | null;
  /** Загрузить всё заново — кнопка «Қайталау» на экране ошибки. */
  reload: () => Promise<void>;
  /** Перезапросить статус (после оплаты, подарка, возврата в приложение). */
  refreshAuth: () => Promise<void>;
  /** Перезапросить витрину, но не чаще раза в полминуты (возврат в приложение). */
  refreshContent: () => Promise<void>;
}

/**
 * `handlers` обязаны быть стабильными (сеттеры состояния или `useCallback`): на них
 * висит эффект первой загрузки, и новая функция на каждый рендер перезагружала бы
 * приложение по кругу.
 */
export function useAppData({ onOpenMovie, onRestoreTab, onToast }: AppDataHandlers): AppData {
  const [phase, setPhase] = useState<Phase>("loading");
  const [auth, setAuth] = useState<Auth | null>(null);
  const [shelves, setShelves] = useState<ShelfData[]>([]);
  const [tariffs, setTariffs] = useState<Tariff[]>([]);
  const [hero, setHero] = useState<Movie | null>(null);
  const [heroFreeUntil, setHeroFreeUntil] = useState<string | null>(null);
  const status: UserStatus = auth?.status ?? "new";

  // Когда каталог был свежим — от этого зависит, тянуть ли его на возврате.
  const contentAt = useRef(0);

  const load = useCallback(async () => {
    // Вне Telegram (открыли URL в обычном браузере) initData пуст → авторизация и весь
    // каталог невозможны. Показываем понятный экран «откройте через Telegram», а не общую
    // ошибку загрузки. В DEV мок бэкенда работает без initData — там не гейтим.
    if (!import.meta.env.DEV && !getInitData()) {
      setPhase("no_telegram");
      return;
    }
    setPhase("loading");
    try {
      const [authRes, homeRes, tariffsRes] = await Promise.all([
        // Авторизация не должна ронять весь экран — каталог смотрят и без неё. Но одну
        // повторную попытку делаем: моргнувшая сеть на первом же запросе иначе лишала бы
        // человека подарка и попапа write-access на весь заход, а починить это могло
        // только свернуть-развернуть приложение (о чём юзер не догадается).
        // `SessionExpiredError` НЕ глушим — она обязана дойти до `catch` ниже.
        retryAuth(),
        api.home(), // hero + все фильмы одним кэшируемым ответом
        api.tariffs(),
      ]);
      setAuth(authRes);
      setShelves(homeRes.shelves);
      setTariffs(tariffsRes);
      setHero(homeRes.hero);
      setHeroFreeUntil(homeRes.hero_free_until ?? null);
      contentAt.current = Date.now(); // каталог только что свежий — не тянуть его повторно
      setPhase("ready");
      // Deep-link (t.me/<bot>?startapp=m_<id>) с SEO-страницы или из поста канала: сразу
      // открываем карточку нужного фильма. Он главнее сохранённого экрана — юзер пришёл
      // по конкретной ссылке.
      //
      // Сбой ОБЪЯСНЯЕМ, а не глотаем: человек нажал кнопку под конкретным фильмом, и
      // молча оказаться на главной для него выглядит как «ссылка не работает». 404 —
      // фильма больше нет; всё остальное — сеть, и стоит попробовать снова.
      const startId = getStartMovieId();
      if (startId !== null) {
        api
          .getMovie(startId)
          .then((movie) => onOpenMovie(movie))
          .catch((e) => {
            onToast(
              e instanceof ApiError && e.status === 404
                ? "Бұл фильм қазір қолжетімсіз. Каталогтан іздеп көріңіз."
                : "Фильмді ашу мүмкін болмады. Байланысты тексеріңіз.",
            );
          });
        return;
      }
      // Иначе продолжаем с того места, где юзера прервали (если это было недавно).
      const last = loadLastPage();
      if (!last) return;
      onRestoreTab(last.tab);
      if (last.movieId !== null) {
        api
          .getMovie(last.movieId)
          .then((movie) => onOpenMovie(movie))
          .catch(() => {}); // фильм удалили — просто открываем вкладку
      }
    } catch (e) {
      // Сессия и initData просрочены вместе — «Қайталау» тут не поможет, поможет только
      // переоткрыть Mini App. Своя фаза и свой экран.
      setPhase(e instanceof SessionExpiredError ? "session_expired" : "error");
    }
  }, [onOpenMovie, onRestoreTab, onToast]);

  useEffect(() => {
    void load();
  }, [load]);

  // ── Свежесть статуса подписки ──
  // Решение по чеку принимает админ ВНЕ приложения (кнопки ✅/❌ у бота), поэтому фронт
  // сам ходит за актуальным статусом: пока «на проверке» — по таймеру, и всегда при
  // возврате на экран. Иначе юзер видел бы «тексерілуде» до полного перезахода в Mini App.
  const statusRef = useRef<UserStatus>(status);
  useEffect(() => {
    statusRef.current = status;
  }, [status]);

  const refreshAuth = useCallback(async () => {
    const before = statusRef.current;
    let fresh: Auth;
    try {
      fresh = await api.me();
    } catch {
      return; // сеть моргнула — попробуем на следующем тике, экран не трогаем
    }
    setAuth(fresh);
    if (before !== "pending_review" || fresh.status === before) return;
    // Модератор только что вынес решение — сообщаем прямо сейчас, не молча.
    if (fresh.has_access) {
      haptic.success();
      onToast("Жазылым қосылды! Көруге болады");
    } else {
      haptic.error();
      onToast("Чек расталмады. Қолдауға жазыңыз");
    }
  }, [onToast]);

  useEffect(() => {
    if (phase !== "ready" || status !== "pending_review") return;
    const timer = setInterval(() => {
      if (!document.hidden) void refreshAuth(); // свёрнутое приложение не опрашиваем
    }, STATUS_POLL_MS);
    return () => clearInterval(timer);
  }, [phase, status, refreshAuth]);

  // Каталог, загруженный при входе, устаревает: админ добавляет фильмы, пока приложение
  // висит свёрнутым. Обновляем его на возврате, но не чаще CONTENT_REFRESH_MS.
  const refreshContent = useCallback(async () => {
    if (Date.now() - contentAt.current < CONTENT_REFRESH_MS) return;
    contentAt.current = Date.now();
    try {
      const fresh = await api.home();
      setShelves(fresh.shelves);
      setHero(fresh.hero);
      setHeroFreeUntil(fresh.hero_free_until ?? null);
    } catch {
      /* не достучались — оставляем то, что уже показано */
    }
  }, []);

  return {
    phase,
    auth,
    setAuth,
    status,
    shelves,
    tariffs,
    hero,
    heroFreeUntil,
    reload: load,
    refreshAuth,
    refreshContent,
  };
}
