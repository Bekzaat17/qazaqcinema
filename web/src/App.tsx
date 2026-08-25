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
import { CatalogEmpty, LoadError, NotInTelegram, SearchEmpty } from "./components/States";
import StatusBanner from "./components/StatusBanner";
import TopBar from "./components/TopBar";
import Toast from "./components/Toast";
import { useAppVersion } from "./hooks/useAppVersion";
import { FavoritesProvider } from "./hooks/useFavorites";
import { useTelegramBackButton } from "./hooks/useTelegramBackButton";
import { ApiError, api, type Auth, type Movie, type Shelf as ShelfData, type Tariff, type UserStatus } from "./lib/api";
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

export default function App() {
  const [phase, setPhase] = useState<"loading" | "ready" | "error" | "no_telegram">("loading");
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
        api.auth().catch(() => null), // авторизация не должна ронять весь экран
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
      // Deep-link с SEO-страницы (t.me/<bot>?startapp=m_<id>): сразу открываем карточку
      // нужного фильма. Сбой (нет такого id) молчаливый — просто остаёмся на главной.
      // Он же главнее сохранённого экрана: юзер пришёл по конкретной ссылке.
      const startId = getStartMovieId();
      if (startId !== null) {
        api
          .getMovie(startId)
          .then((movie) => setSelected(movie))
          .catch(() => {});
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
    } catch {
      setPhase("error");
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
  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setResults(null);
      setSearching(false);
      return;
    }
    setSearching(true);
    const id = ++reqId.current;
    const timer = setTimeout(() => {
      api
        .searchMovies(q)
        .then((res) => {
          if (id === reqId.current) setResults(res);
        })
        .catch(() => {
          if (id === reqId.current) setResults([]);
        })
        .finally(() => {
          if (id === reqId.current) setSearching(false);
        });
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

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
          setToast("Қате шықты, қайталап көріңіз");
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

      {phase === "ready" &&
        tab === "home" &&
        (results !== null ? (
          <SearchResults query={query} results={results} searching={searching} onSelect={setSelected} />
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
      <HandoffModal open={handoffOpen} gift={handoffGift} daily={handoffDaily} />
      {toast && <Toast message={toast} onDone={() => setToast(null)} />}
    </div>
    </FavoritesProvider>
  );
}

function SearchResults({
  query,
  results,
  searching,
  onSelect,
}: {
  query: string;
  results: Movie[];
  searching: boolean;
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
  if (results.length === 0) return <SearchEmpty query={query} />;
  return (
    <div className="grid grid-cols-3 gap-3 px-4 pt-4">
      {results.map((movie) => (
        <PosterCard key={movie.id} movie={movie} onSelect={onSelect} inShelf={false} />
      ))}
    </div>
  );
}
