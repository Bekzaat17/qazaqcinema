// Оркестратор Mini App: загрузка (auth + каталог + тарифы), главный экран, поиск и стек
// оверлеев (карточка → пэйволл, профиль, хэндофф-модалка). Один экран, навигация — состоянием.

import { useCallback, useEffect, useRef, useState } from "react";

import CatalogView from "./components/CatalogView";
import Hero from "./components/Hero";
import HandoffModal from "./components/HandoffModal";
import HomeSkeleton from "./components/HomeSkeleton";
import MovieSheet from "./components/MovieSheet";
import Paywall from "./components/Paywall";
import PosterCard from "./components/PosterCard";
import ProfileSheet from "./components/ProfileSheet";
import SearchBar from "./components/SearchBar";
import Shelf from "./components/Shelf";
import TabBar, { type Tab } from "./components/TabBar";
import { CatalogEmpty, LoadError, NotInTelegram, SearchEmpty } from "./components/States";
import StatusBanner from "./components/StatusBanner";
import TopBar from "./components/TopBar";
import Toast from "./components/Toast";
import { useTelegramBackButton } from "./hooks/useTelegramBackButton";
import { ApiError, api, type Auth, type Movie, type Shelf as ShelfData, type Tariff } from "./lib/api";
import { getInitData, haptic } from "./lib/telegram";
import Skeleton from "./ui/Skeleton";

export default function App() {
  const [phase, setPhase] = useState<"loading" | "ready" | "error" | "no_telegram">("loading");
  const [auth, setAuth] = useState<Auth | null>(null);
  const [shelves, setShelves] = useState<ShelfData[]>([]);
  const [tariffs, setTariffs] = useState<Tariff[]>([]);
  const [hero, setHero] = useState<Movie | null>(null);
  const [tab, setTab] = useState<Tab>("home");

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Movie[] | null>(null);
  const [searching, setSearching] = useState(false);

  const [selected, setSelected] = useState<Movie | null>(null);
  const [paywallOpen, setPaywallOpen] = useState(false);
  const [paywallMovie, setPaywallMovie] = useState<Movie | null>(null);
  const [profileOpen, setProfileOpen] = useState(false);
  const [handoffOpen, setHandoffOpen] = useState(false);
  const [watching, setWatching] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const status = auth?.status ?? "new";
  const hasAccess = auth?.has_access ?? false;

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
      setPhase("ready");
    } catch {
      setPhase("error");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

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
  const anyOverlay = handoffOpen || paywallOpen || !!selected || profileOpen;
  const onBack = useCallback(() => {
    if (handoffOpen) setHandoffOpen(false);
    else if (paywallOpen) setPaywallOpen(false);
    else if (selected) setSelected(null);
    else if (profileOpen) setProfileOpen(false);
    else if (tab === "catalog") setTab("home");
  }, [handoffOpen, paywallOpen, selected, profileOpen, tab]);
  useTelegramBackButton(anyOverlay || tab === "catalog", onBack);

  const openPaywall = useCallback((movie: Movie | null) => {
    setPaywallMovie(movie);
    setPaywallOpen(true);
  }, []);

  const handleWatch = useCallback(
    async (movie: Movie) => {
      if (!hasAccess) {
        haptic.warning();
        openPaywall(movie);
        return;
      }
      setWatching(true);
      try {
        await api.play(movie.id);
        haptic.success();
        setSelected(null);
        setHandoffOpen(true);
      } catch (e) {
        if (e instanceof ApiError && e.status === 403) {
          openPaywall(movie); // доступ устарел — сервер источник правды
        } else if (e instanceof ApiError && e.status === 404) {
          setToast("Фильм табылмады");
        } else if (e instanceof ApiError && e.status === 409) {
          setToast("Алдымен ботпен чатты ашыңыз"); // видео шлётся в чат — его надо начать
        } else {
          setToast("Қате шықты, қайталап көріңіз");
        }
      } finally {
        setWatching(false);
      }
    },
    [hasAccess, openPaywall],
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
            {hero && <Hero movie={hero} onSelect={setSelected} />}
            {shelves.map((shelf) => (
              <Shelf key={shelf.key} shelf={shelf} onSelect={setSelected} />
            ))}
          </div>
        ))}

      {phase === "ready" && tab === "catalog" && <CatalogView onSelect={setSelected} />}

      {phase === "ready" && <TabBar tab={tab} onChange={setTab} />}

      <MovieSheet
        movie={selected}
        hasAccess={hasAccess}
        status={status}
        busy={watching}
        onWatch={handleWatch}
        onClose={() => setSelected(null)}
      />
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
        onNotificationsChange={(enabled) =>
          setAuth((prev) => (prev ? { ...prev, notifications_enabled: enabled } : prev))
        }
      />
      <HandoffModal open={handoffOpen} />
      {toast && <Toast message={toast} onDone={() => setToast(null)} />}
    </div>
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
