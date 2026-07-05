// Оркестратор Mini App: загрузка (auth + каталог + тарифы), главный экран, поиск и стек
// оверлеев (карточка → пэйволл, профиль, хэндофф-модалка). Один экран, навигация — состоянием.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import Hero from "./components/Hero";
import HandoffModal from "./components/HandoffModal";
import HomeSkeleton from "./components/HomeSkeleton";
import MovieSheet from "./components/MovieSheet";
import Paywall from "./components/Paywall";
import PosterCard from "./components/PosterCard";
import ProfileSheet from "./components/ProfileSheet";
import SearchBar from "./components/SearchBar";
import Shelf from "./components/Shelf";
import { CatalogEmpty, LoadError, SearchEmpty } from "./components/States";
import StatusBanner from "./components/StatusBanner";
import TopBar from "./components/TopBar";
import Toast from "./components/Toast";
import { useTelegramBackButton } from "./hooks/useTelegramBackButton";
import { ApiError, api, type Auth, type Movie, type Tariff } from "./lib/api";
import { buildShelves } from "./lib/catalog";
import { haptic } from "./lib/telegram";
import Skeleton from "./ui/Skeleton";

export default function App() {
  const [phase, setPhase] = useState<"loading" | "ready" | "error">("loading");
  const [auth, setAuth] = useState<Auth | null>(null);
  const [movies, setMovies] = useState<Movie[]>([]);
  const [tariffs, setTariffs] = useState<Tariff[]>([]);
  const [hero, setHero] = useState<Movie | null>(null);

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
    setPhase("loading");
    try {
      const [authRes, homeRes, tariffsRes] = await Promise.all([
        api.auth().catch(() => null), // авторизация не должна ронять весь экран
        api.home(), // hero + все фильмы одним кэшируемым ответом (Фаза 11.2)
        api.tariffs(),
      ]);
      setAuth(authRes);
      setMovies(homeRes.movies);
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

  // Единая нативная кнопка «назад» на весь стек оверлеев (сверху вниз).
  const anyOverlay = handoffOpen || paywallOpen || !!selected || profileOpen;
  const onBack = useCallback(() => {
    if (handoffOpen) setHandoffOpen(false);
    else if (paywallOpen) setPaywallOpen(false);
    else if (selected) setSelected(null);
    else if (profileOpen) setProfileOpen(false);
  }, [handoffOpen, paywallOpen, selected, profileOpen]);
  useTelegramBackButton(anyOverlay, onBack);

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

  const { shelves } = useMemo(() => buildShelves(movies, hero?.id), [movies, hero]);

  return (
    <div className="min-h-screen bg-bg pb-[calc(28px+var(--safe-bottom))]">
      <TopBar status={status} onProfile={() => setProfileOpen(true)} />

      {phase === "ready" && <SearchBar value={query} onChange={setQuery} />}
      {phase === "ready" && status === "pending_review" && <StatusBanner />}

      {phase === "loading" && <HomeSkeleton />}
      {phase === "error" && <LoadError onRetry={load} />}

      {phase === "ready" &&
        (results !== null ? (
          <SearchResults query={query} results={results} searching={searching} onSelect={setSelected} />
        ) : movies.length === 0 ? (
          <CatalogEmpty />
        ) : (
          <div className="pb-2">
            {hero && <Hero movie={hero} onSelect={setSelected} />}
            {shelves.map((shelf) => (
              <Shelf key={shelf.key} shelf={shelf} onSelect={setSelected} />
            ))}
          </div>
        ))}

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
