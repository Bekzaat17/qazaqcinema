// Оркестратор Mini App: загрузка (auth + каталог + тарифы), главный экран, поиск и стек
// оверлеев (карточка → пэйволл, профиль, хэндофф-модалка). Один экран, навигация — состоянием.

import { useCallback, useEffect, useRef, useState } from "react";

import BotStartSheet from "./components/BotStartSheet";
import CatalogView from "./components/CatalogView";
import FavoritesView from "./components/FavoritesView";
import GiftSheet from "./components/GiftSheet";
import Hero from "./components/Hero";
import HandoffModal from "./components/HandoffModal";
import HomeSkeleton from "./components/HomeSkeleton";
import MovieSheet from "./components/MovieSheet";
import Paywall from "./components/Paywall";
import PosterCard from "./components/PosterCard";
import ProfileSheet from "./components/ProfileSheet";
import SearchBar from "./components/SearchBar";
import Shelf from "./components/Shelf";
import SupportSheet from "./components/SupportSheet";
import TabBar, { type Tab } from "./components/TabBar";
import {
  CatalogEmpty,
  LoadError,
  NotInTelegram,
  SearchEmpty,
  SearchFailed,
  SessionExpired,
} from "./components/States";
import StatusBanner from "./components/StatusBanner";
import TopBar from "./components/TopBar";
import Toast from "./components/Toast";
import { useAppVersion } from "./hooks/useAppVersion";
import { FavoritesProvider } from "./hooks/useFavorites";
import { useTelegramBackButton } from "./hooks/useTelegramBackButton";
import {
  ApiError,
  NetworkError,
  SessionExpiredError,
  api,
  type Auth,
  type Movie,
  type Shelf as ShelfData,
  type Tariff,
  type UserStatus,
} from "./lib/api";
import { loadLastPage, saveLastPage } from "./lib/lastPage";
import { getInitData, getStartMovieId, haptic, requestWriteAccess } from "./lib/telegram";
import Skeleton from "./ui/Skeleton";

// Как часто переспрашивать статус, пока чек «на проверке». Решение админа (✅/❌) приходит
// извне приложения, поэтому фронт узнаёт о нём только опросом. 20 с — незаметно для юзера
// и всего 3 запроса в минуту (лимит `/api/me` — 120/мин на IP, см. api/routers/me.py).
const STATUS_POLL_MS = 20_000;

// Не чаще этого перезапрашиваем каталог при возврате в приложение. Полминуты хватает,
// чтобы новинка, добавленная админом, появилась сама, и при этом «свернул-развернул»
// десять раз подряд не превращается в десять запросов.
const CONTENT_REFRESH_MS = 30_000;

// Пауза перед попапом «разрешить боту писать». Нужна, чтобы человек успел увидеть, КУДА
// он попал: системный запрос поверх голого скелета выглядит как требование неизвестно от
// кого, и его закрывают не читая. Полсекунды — главная уже отрисована, приложение ещё не
// пролистано.
const WRITE_ACCESS_PROMPT_MS = 600;

// Через сколько тишины в наборе считаем запрос ЗАКОНЧЕННЫМ и пишем его в спрос.
// Заметно больше дебаунса поиска (300 мс) — и в этом весь смысл: набирая «кунг фу
// панда», человек по пути отправляет серверу «кун», «кунг ф», «кунг фу пан», и в
// статистику спроса такие огрызки попадать не должны — иначе очередь на озвучку
// («искали, но не нашли») состояла бы из недонабранных слов. Таймер сбрасывается на
// каждое изменение запроса, поэтому доживает до конца только та строка, на которой
// человек реально остановился.
const SEARCH_TRACK_MS = 1_200;

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

/**
 * Текст ошибки для тоста. Каждый случай — свой совет, потому что действия разные:
 * проверить связь / подождать / попробовать снова.
 *
 * До этого всё сводилось к одному «қате шықты, қайталап көріңіз», и на 429 человек по
 * этому совету жал снова, только усугубляя лимит.
 */
function failureText(e: unknown): string {
  if (e instanceof NetworkError) return "Байланыс жоқ. Қайталап көріңіз.";
  if (!(e instanceof ApiError)) return "Қате шықты, қайталап көріңіз";
  // 429 — наш лимитер (ключ по IP, а мобильные сидят за общим CGNAT).
  // 503 — Telegram не принял отправку сейчас (флуд-лимит на всплеске, сеть, 5xx).
  // Оба лечатся паузой, а не повтором вплотную, — так и говорим.
  if (e.status === 429 || e.status === 503) return "Сәл күте тұрып, қайталаңыз.";
  return "Қате шықты, қайталап көріңіз";
}

export default function App() {
  // `session_expired` — отдельная фаза, а не разновидность `error`: лечение у неё другое
  // (переоткрыть Mini App, а не «повторить»), и без неё приложение оставалось бы с виду
  // рабочим, отвечая «қате шықты» на каждое нажатие (см. `SessionExpiredError`).
  const [phase, setPhase] = useState<
    "loading" | "ready" | "error" | "no_telegram" | "session_expired"
  >("loading");
  const [auth, setAuth] = useState<Auth | null>(null);
  const [shelves, setShelves] = useState<ShelfData[]>([]);
  const [tariffs, setTariffs] = useState<Tariff[]>([]);
  const [hero, setHero] = useState<Movie | null>(null);
  // До какого момента hero (он же фильм дня) бесплатен. null → каталог пуст либо бэк
  // старой версии: hero тогда обычная витрина, без бейджа и таймера.
  const [heroFreeUntil, setHeroFreeUntil] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("home");

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Movie[] | null>(null);
  const [searching, setSearching] = useState(false);
  // Отдельно от `results === []`: «не нашлось» и «не смог спросить» — разные ответы юзеру.
  const [searchFailed, setSearchFailed] = useState(false);

  const [selected, setSelected] = useState<Movie | null>(null);
  const [paywallOpen, setPaywallOpen] = useState(false);
  const [paywallMovie, setPaywallMovie] = useState<Movie | null>(null);
  const [profileOpen, setProfileOpen] = useState(false);
  const [supportOpen, setSupportOpen] = useState(false);
  const [handoffOpen, setHandoffOpen] = useState(false);
  const [handoffGift, setHandoffGift] = useState(false);
  const [handoffDaily, setHandoffDaily] = useState(false);
  const [giftOpen, setGiftOpen] = useState(false);
  const [botStartOpen, setBotStartOpen] = useState(false);
  const [giftMovie, setGiftMovie] = useState<Movie | null>(null);
  const [watching, setWatching] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  // Объявлены здесь, а не рядом с местом использования: на них завязан эффект «возврат в
  // приложение» ниже, а обращение к const из его списка зависимостей до объявления —
  // ошибка времени выполнения (временная мёртвая зона), а не просто нестройность.
  const updateReady = useAppVersion();
  const anyOverlay =
    handoffOpen ||
    paywallOpen ||
    giftOpen ||
    botStartOpen ||
    supportOpen ||
    !!selected ||
    profileOpen;

  const status = auth?.status ?? "new";
  const hasAccess = auth?.has_access ?? false;
  // Подарочный первый фильм. Пока авторизация не доехала, считаем подарок недоступным:
  // ложное приглашение с последующим 403 хуже, чем пэйволл, который сервер подтвердит.
  const freeViewAvailable = auth?.free_view_available ?? false;
  const giftedMovieId = auth?.free_view_movie_id ?? null;
  // Фильм дня: бесплатен сегодня всем и подарка НЕ тратит. Признак берём из hero — тот
  // же источник, что и у выдачи (бэк сверяет id сам), поэтому «Тегін көру» не может
  // привести к 403.
  const dailyMovieId = heroFreeUntil !== null ? (hero?.id ?? null) : null;
  // Чат с ботом. Пока авторизация не доехала — считаем, что он есть: ложная шторка
  // «откройте бота» тем, у кого всё в порядке, хуже, чем один честный 409 от сервера.
  const botStarted = auth?.bot_started ?? true;

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
        api.home(), // hero + все фильмы одним кэшируемым ответом (Фаза 11.2)
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
          .then((movie) => setSelected(movie))
          .catch((e) => {
            setToast(
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
      setTab(last.tab);
      if (last.movieId !== null) {
        api
          .getMovie(last.movieId)
          .then((movie) => setSelected(movie))
          .catch(() => {}); // фильм удалили — просто открываем вкладку
      }
    } catch (e) {
      // Сессия и initData просрочены вместе — «Қайталау» тут не поможет, поможет только
      // переоткрыть Mini App. Своя фаза и свой экран.
      setPhase(e instanceof SessionExpiredError ? "session_expired" : "error");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // ── Свежесть статуса подписки ──
  // Решение по чеку принимает админ ВНЕ приложения (кнопки ✅/❌ у бота), поэтому фронт
  // сам ходит за актуальным статусом: пока «на проверке» — по таймеру, и всегда при
  // возврате на экран. Раньше юзер видел «тексерілуде» до полного перезахода в Mini App.
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
      setToast("Жазылым қосылды! Көруге болады");
    } else {
      haptic.error();
      setToast("Чек расталмады. Қолдауға жазыңыз");
    }
  }, []);

  useEffect(() => {
    if (phase !== "ready" || status !== "pending_review") return;
    const timer = setInterval(() => {
      if (!document.hidden) void refreshAuth(); // свёрнутое приложение не опрашиваем
    }, STATUS_POLL_MS);
    return () => clearInterval(timer);
  }, [phase, status, refreshAuth]);

  // Каталог, загруженный при входе, устаревает: админ добавляет фильмы, пока приложение
  // висит свёрнутым. Обновляем его на возврате, но не чаще CONTENT_REFRESH_MS.
  const contentAt = useRef(0);
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

  useEffect(() => {
    if (phase !== "ready") return;
    // Возврат из чата с ботом (там же приходит DM об активации) — самый частый момент,
    // когда статус уже поменялся, а экран об этом ещё не знает.
    const onResume = () => {
      if (document.hidden) return;
      // Вышла новая версия приложения — применяем её ИМЕННО ЗДЕСЬ. Человек только что
      // вернулся в приложение, ничего не заполняет, и перезагрузка для него неотличима
      // от обычного открытия. Но не поверх открытой шторки: посреди оплаты или загрузки
      // чека reload стёр бы наполовину пройденный шаг.
      if (updateReady && !anyOverlay) {
        window.location.reload();
        return;
      }
      void refreshAuth();
      void refreshContent();
    };
    document.addEventListener("visibilitychange", onResume);
    window.addEventListener("focus", onResume);
    return () => {
      document.removeEventListener("visibilitychange", onResume);
      window.removeEventListener("focus", onResume);
    };
  }, [phase, refreshAuth, refreshContent, updateReady, anyOverlay]);

  // Человек сходил в бота и вернулся — шторка «Ботты ашу» больше не нужна и должна уйти
  // сама. Держать её открытой поверх готового к работе приложения значит требовать ещё
  // одно действие ровно после того, как человек сделал то, о чём просили.
  useEffect(() => {
    if (botStarted) setBotStartOpen(false);
  }, [botStarted]);

  // Право боту писать в личку — просим САМИ, на входе, нативным попапом Telegram.
  //
  // Без этого права кинотеатр для человека не работает вообще: фильм уходит сообщением, а
  // первым бот писать не вправе. Раньше единственной дорогой был поход в чат за кнопкой
  // START — и по живым данным на нём останавливались 34 человека из 123, ни один из
  // которых не посмотрел ни одного фильма. Попап решает то же самое одним нажатием, не
  // сворачивая приложение.
  //
  // Спрашиваем один раз за заход (ref, а не state — перерисовка не должна открывать попап
  // заново) и только когда права ещё нет. Отказ и старый клиент оставляют всё как было:
  // шторка `BotStartSheet` с дорогой в чат никуда не делась и покажется на «Көру».
  const writeAccessAsked = useRef(false);
  useEffect(() => {
    if (phase !== "ready" || botStarted || writeAccessAsked.current) return;
    writeAccessAsked.current = true;
    const timer = setTimeout(() => {
      void (async () => {
        if (!(await requestWriteAccess())) return;
        haptic.success();
        try {
          setAuth(await api.grantWriteAccess());
        } catch {
          // Сеть моргнула на записи факта — состояние всё равно поднимаем: отправка
          // видео от признака не зависит, а успешная доставка чинит флаг на бэке сама
          // (`PlaybackService` проставляет его при первой же удачной выдаче).
          setAuth((prev) => (prev ? { ...prev, bot_started: true } : prev));
        }
      })();
    }, WRITE_ACCESS_PROMPT_MS);
    return () => clearTimeout(timer);
  }, [phase, botStarted]);

  // Запоминаем экран (вкладка + открытая карточка) — чтобы вернуть его при заходе в
  // ближайший час. Пишем на каждое изменение: заход можно и не «закрыть» по-человечески.
  useEffect(() => {
    if (phase !== "ready") return;
    saveLastPage({ tab, movieId: selected?.id ?? null });
  }, [phase, tab, selected]);

  // Поиск с дебаунсом; гонки гасим монотонным reqId.
  const reqId = useRef(0);
  // Счётчик ручных повторов: запрос тот же, а эффект перезапустить надо (кнопка
  // «Қайталау» на сбое поиска). Через deps — а не вызовом функции поиска напрямую,
  // чтобы повтор шёл ровно тем же путём, что и обычный ввод.
  const [searchNonce, setSearchNonce] = useState(0);
  const retrySearch = useCallback(() => {
    setSearchFailed(false);
    setSearchNonce((n) => n + 1);
  }, []);
  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setResults(null);
      setSearchFailed(false);
      setSearching(false);
      return;
    }
    setSearching(true);
    const id = ++reqId.current;
    const timer = setTimeout(() => {
      api
        .searchMovies(q)
        .then((res) => {
          if (id !== reqId.current) return;
          setSearchFailed(false);
          setResults(res);
        })
        .catch(() => {
          // ⚠️ НЕ `setResults([])`: пустой массив рисует «Ештеңе табылмады», то есть
          // приложение уверенно сообщало бы «такого фильма у нас нет» на обычном обрыве
          // связи. Для человека, пришедшего за конкретным названием, это дезинформация —
          // он уйдёт, решив, что фильма нет. Ошибку показываем ошибкой.
          if (id !== reqId.current) return;
          setSearchFailed(true);
          setResults(null);
        })
        .finally(() => {
          if (id === reqId.current) setSearching(false);
        });
    }, 300);
    return () => clearTimeout(timer);
  }, [query, searchNonce]);

  // Спрос словами: пишем запрос и сколько по нему нашлось. Отдельным эффектом от самого
  // поиска, с собственной, более длинной паузой (SEARCH_TRACK_MS) — сервер по своим
  // запросам не может отличить законченный запрос от префикса недонабранного слова.
  // Ноль результатов здесь — самая ценная строка: человек назвал, за чем пришёл, и ушёл
  // ни с чем, а из таких запросов и собирается очередь на озвучку.
  useEffect(() => {
    const q = query.trim();
    if (q.length < 2 || results === null) return;
    const found = results.length;
    const timer = setTimeout(() => {
      // Фоном и молча: аналитика спроса не имеет права ни задержать выдачу результатов,
      // ни всплыть ошибкой перед человеком (тот же принцип, что у trackPaywall).
      void api.trackSearch(q, found).catch(() => {});
    }, SEARCH_TRACK_MS);
    return () => clearTimeout(timer);
  }, [query, results]);

  // Единая нативная кнопка «назад»: закрывает оверлеи (сверху вниз), а на вкладке
  // «Каталог» без оверлеев — возвращает на «Басты» (таб — не оверлей, но выход логичен).
  const onBack = useCallback(() => {
    if (handoffOpen) setHandoffOpen(false);
    else if (paywallOpen) setPaywallOpen(false);
    else if (giftOpen) setGiftOpen(false);
    else if (supportOpen) setSupportOpen(false);
    else if (selected) setSelected(null);
    else if (botStartOpen) setBotStartOpen(false);
    else if (profileOpen) setProfileOpen(false);
    else if (tab !== "home") setTab("home");
  }, [handoffOpen, paywallOpen, giftOpen, botStartOpen, supportOpen, selected, profileOpen, tab]);
  useTelegramBackButton(anyOverlay || tab !== "home", onBack);

  /**
   * Показать пэйволл. `track` — писать ли событие воронки (по умолчанию да).
   *
   * Логируем ИМЕННО здесь: это единственное место, через которое проходят все дороги к
   * пэйволлу, и единственный способ для сервера вообще узнать о нём — решение «доступа
   * нет» фронт принимает сам, ничего не спрашивая. `track: false` передаётся там, где
   * сервер уже записал событие своей стороной (ответ 403 на «Көру»), иначе один упор
   * считался бы дважды.
   */
  const openPaywall = useCallback((movie: Movie | null, track = true) => {
    setPaywallMovie(movie);
    setPaywallOpen(true);
    // Фоном и без ожидания: метрика не имеет права задерживать шторку или ронять её
    // показ, если запрос не прошёл.
    if (track) void api.trackPaywall(movie?.id ?? null).catch(() => {});
  }, []);

  /** Отправка видео. `useFreeView` — согласие потратить подарок (только из GiftSheet). */
  const requestPlay = useCallback(
    async (movie: Movie, useFreeView: boolean) => {
      setWatching(true);
      try {
        const res = await api.play(movie.id, useFreeView);
        haptic.success();
        setSelected(null);
        setGiftOpen(false);
        setHandoffGift(res.gift);
        setHandoffDaily(res.daily);
        setHandoffOpen(true);
        // Подарок потрачен — состояние живёт на сервере, поэтому забираем его свежим:
        // от этого зависит, что покажут остальные фильмы (приглашение или пэйволл).
        if (res.gift) void refreshAuth();
      } catch (e) {
        if (e instanceof ApiError && e.status === 403) {
          setGiftOpen(false);
          // Доступ устарел — сервер источник правды. Событие пэйволла он записал сам
          // (`PlaybackService` пишет его на отказе), поэтому здесь не дублируем.
          openPaywall(movie, false);
        } else if (e instanceof ApiError && e.status === 404) {
          setToast("Фильм табылмады");
        } else if (e instanceof ApiError && e.status === 409) {
          // Сервер не достучался до лички: чат закрыт или бот заблокирован. Он уже снял
          // признак у себя — снимаем и локально, чтобы следующее «Көру» вело в бота сразу.
          setGiftOpen(false);
          setAuth((prev) => (prev ? { ...prev, bot_started: false } : prev));
          setBotStartOpen(true);
        } else {
          // Сеть, таймаут, 429, 5xx (например, флуд-лимит Telegram на всплеске из канала).
          // Совет юзеру в каждом случае разный, и общее «қате шықты» на 429 толкало его
          // жать снова, только усугубляя лимит.
          setToast(failureText(e));
        }
      } finally {
        setWatching(false);
      }
    },
    [openPaywall, refreshAuth],
  );

  const handleWatch = useCallback(
    async (movie: Movie) => {
      // Порядок ветвей = порядок воронки: подписка → фильм дня → свой подаренный фильм →
      // приглашение к подарку → пэйволл. Платить просим ПОСЛЕДНИМ и только когда предложить
      // больше нечего — в этом весь смысл «сначала ценность, потом оплата». Фильм дня идёт
      // до подарка: он бесплатен сам по себе, и тратить на него подарок (или показывать
      // шторку «потратить сыйлық?») было бы обманом.
      //
      // Про чат с ботом здесь НЕ спрашиваем: в этих трёх случаях попытка ничего не стоит,
      // а признак у нас может быть устаревшим (человек начал чат до появления колонки).
      // Не дошло — сервер ответит 409, и шторку покажет обработчик ошибки; дошло — флаг
      // на бэке починится сам. Так мы не гоним в бота тех, у кого и так всё работает.
      if (hasAccess || movie.id === dailyMovieId || movie.id === giftedMovieId) {
        await requestPlay(movie, false);
        return;
      }
      // Авторизация не доехала (сеть моргнула на входе) — мы НЕ ЗНАЕМ, есть ли подарок и
      // доступ. Единственное, чего тут нельзя делать, — показывать пэйволл: человек,
      // пришедший из канала за бесплатным фильмом дня, получил бы просьбу заплатить за
      // то, что ему положено даром, хотя сервер отдал бы это без вопросов
      // (`PlaybackService._resolve_gift` считает права сам). Поэтому спрашиваем сервер:
      // отдаст — покажем видео, откажет — 403 откроет пэйволл уже по правде.
      // Подарок при этом не тратим (`useFreeView=false`): его расход требует явного
      // согласия в шторке, а мы даже не знаем, цел ли он.
      if (auth === null) {
        await requestPlay(movie, false);
        return;
      }
      if (freeViewAvailable) {
        // А вот тут проверяем ДО: на кону единственный подарок, и «попробуем — узнаем»
        // означало бы риск потратить его на отправку, которая не дойдёт.
        if (!botStarted) {
          haptic.warning();
          setBotStartOpen(true);
          return;
        }
        // Подарок не тратим здесь: сначала человек видит, что именно ему дарят, и
        // подтверждает. Тратит его уже `onAccept` шторки.
        haptic.light();
        setGiftMovie(movie);
        setGiftOpen(true);
        return;
      }
      haptic.warning();
      openPaywall(movie);
    },
    [
      auth,
      botStarted,
      hasAccess,
      dailyMovieId,
      giftedMovieId,
      freeViewAvailable,
      requestPlay,
      openPaywall,
    ],
  );

  const handlePending = useCallback(() => {
    setAuth((prev) => (prev ? { ...prev, status: "pending_review" } : prev));
    setPaywallOpen(false);
    setSelected(null);
    setToast("Чек қабылданды — тексерудеміз");
  }, []);

  const handlePaid = useCallback(async () => {
    setPaywallOpen(false);
    setToast("Төлем сәтті өтті!");
    try {
      setAuth(await api.auth());
    } catch {
      /* обновим статус при следующем заходе */
    }
  }, []);

  return (
    // Провайдер избранного включаем только когда приложение готово: до авторизации
    // ручка отдала бы 401, а звёзды всё равно некуда рисовать.
    <FavoritesProvider enabled={phase === "ready"}>
    <div className="min-h-screen bg-bg pb-[calc(72px+var(--safe-bottom))]">
      <TopBar status={status} onProfile={() => setProfileOpen(true)} />

      {phase === "ready" && tab === "home" && <SearchBar value={query} onChange={setQuery} />}
      {phase === "ready" && tab === "home" && status === "pending_review" && <StatusBanner />}

      {phase === "loading" && <HomeSkeleton />}
      {phase === "error" && <LoadError onRetry={load} />}
      {phase === "no_telegram" && <NotInTelegram />}
      {phase === "session_expired" && <SessionExpired />}

      {phase === "ready" &&
        tab === "home" &&
        // `searchFailed` тоже открывает панель поиска: на сбое `results` = null, и без
        // этого условия юзер вместо объяснения увидел бы главную с полками — как будто
        // поиск и не запускался.
        (results !== null || searchFailed ? (
          <SearchResults
            query={query}
            results={results ?? []}
            searching={searching}
            failed={searchFailed}
            // Повтор без нового ввода: дёргаем тот же запрос заново, меняя reqId.
            onRetry={retrySearch}
            onSelect={setSelected}
          />
        ) : shelves.length === 0 && !hero ? (
          <CatalogEmpty />
        ) : (
          <div className="pb-2">
            {hero && (
              <Hero
                movie={hero}
                freeUntil={heroFreeUntil}
                busy={watching}
                onSelect={setSelected}
                onWatch={handleWatch}
              />
            )}
            {shelves.map((shelf) => (
              <Shelf key={shelf.key} shelf={shelf} onSelect={setSelected} />
            ))}
          </div>
        ))}

      {phase === "ready" && tab === "catalog" && <CatalogView onSelect={setSelected} />}
      {phase === "ready" && tab === "favorites" && <FavoritesView onSelect={setSelected} />}

      {phase === "ready" && <TabBar tab={tab} onChange={setTab} />}

      <MovieSheet
        movie={selected}
        hasAccess={hasAccess}
        status={status}
        busy={watching}
        freeViewAvailable={freeViewAvailable}
        gifted={selected?.id === giftedMovieId}
        freeToday={selected?.id === dailyMovieId}
        onWatch={handleWatch}
        onClose={() => setSelected(null)}
      />
      <GiftSheet
        open={giftOpen}
        movie={giftMovie}
        busy={watching}
        onAccept={(movie) => void requestPlay(movie, true)}
        onClose={() => setGiftOpen(false)}
      />
      <BotStartSheet open={botStartOpen} onClose={() => setBotStartOpen(false)} />
      <Paywall
        open={paywallOpen}
        movie={paywallMovie}
        tariffs={tariffs}
        onClose={() => setPaywallOpen(false)}
        onPending={handlePending}
        onPaid={handlePaid}
        onError={setToast}
      />
      <ProfileSheet
        open={profileOpen}
        auth={auth}
        onClose={() => setProfileOpen(false)}
        onSubscribe={() => {
          setProfileOpen(false);
          openPaywall(null);
        }}
        onSupport={() => {
          setProfileOpen(false); // одна шторка за раз: профиль уступает место обращению
          setSupportOpen(true);
        }}
        onNotificationsChange={(enabled) =>
          setAuth((prev) => (prev ? { ...prev, notifications_enabled: enabled } : prev))
        }
      />
      <SupportSheet
        open={supportOpen}
        onClose={() => setSupportOpen(false)}
        onSent={setToast}
        onError={setToast}
      />
      <HandoffModal
        open={handoffOpen}
        gift={handoffGift}
        daily={handoffDaily}
        onClose={() => setHandoffOpen(false)}
      />
      {toast && <Toast message={toast} onDone={() => setToast(null)} />}
    </div>
    </FavoritesProvider>
  );
}

function SearchResults({
  query,
  results,
  searching,
  failed,
  onRetry,
  onSelect,
}: {
  query: string;
  results: Movie[];
  searching: boolean;
  failed: boolean;
  onRetry: () => void;
  onSelect: (m: Movie) => void;
}) {
  if (searching && results.length === 0) {
    return (
      <div className="grid grid-cols-3 gap-3 px-4 pt-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="aspect-[2/3] w-full" />
        ))}
      </div>
    );
  }
  // Сбой проверяем ДО «пусто»: иначе обрыв связи выглядел бы как «фильма нет».
  if (failed) return <SearchFailed onRetry={onRetry} />;
  if (results.length === 0) return <SearchEmpty query={query} />;
  return (
    <div className="grid grid-cols-3 gap-3 px-4 pt-4">
      {results.map((movie) => (
        <PosterCard key={movie.id} movie={movie} onSelect={onSelect} inShelf={false} />
      ))}
    </div>
  );
}
