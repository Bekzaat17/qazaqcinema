// Оркестратор Mini App: главный экран, стек оверлеев (карточка → пэйволл, профиль,
// хэндофф-модалка) и правила продукта — кому что показать на «Көру». Один экран,
// навигация — состоянием. Как добываются данные, ищутся фильмы и просится право писать —
// в хуках `useAppData`, `useSearch`, `useWriteAccessPrompt`.

import { useCallback, useEffect, useState } from "react";

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
import { useAppData } from "./hooks/useAppData";
import { useAppVersion } from "./hooks/useAppVersion";
import { FavoritesProvider } from "./hooks/useFavorites";
import { useOnResume } from "./hooks/useOnResume";
import { useSearch } from "./hooks/useSearch";
import { useTelegramBackButton } from "./hooks/useTelegramBackButton";
import { useWriteAccessPrompt } from "./hooks/useWriteAccessPrompt";
import { ApiError, NetworkError, api, type Movie } from "./lib/api";
import { saveLastPage } from "./lib/lastPage";
import { haptic } from "./lib/telegram";
import Skeleton from "./ui/Skeleton";

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
  const [tab, setTab] = useState<Tab>("home");
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

  // Сеттеры состояния (стабильные) — то, чем хук данных открывает карточку по deep-link,
  // возвращает прошлую вкладку и сообщает о решении по чеку.
  const {
    phase,
    auth,
    setAuth,
    status,
    shelves,
    tariffs,
    hero,
    heroFreeUntil,
    reload,
    refreshAuth,
    refreshContent,
  } = useAppData({ onOpenMovie: setSelected, onRestoreTab: setTab, onToast: setToast });
  const search = useSearch();

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

  // Возврат из чата с ботом (там же приходит DM об активации) — самый частый момент,
  // когда статус уже поменялся, а экран об этом ещё не знает.
  const onResume = useCallback(() => {
    // Подтверждение «видео отправлено» живёт ровно до ухода в чат. Свёрнутая Mini App
    // не умирает, и без этой строки человек, вернувшийся из чата (где он видео и
    // посмотрел), снова упирается в модалку о том, что давно случилось, — приложение
    // выглядит застрявшим на шаге, который он прошёл.
    setHandoffOpen(false);
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
  }, [updateReady, anyOverlay, refreshAuth, refreshContent]);
  useOnResume(phase === "ready", onResume);

  // Человек сходил в бота и вернулся — шторка «Ботты ашу» больше не нужна и должна уйти
  // сама. Держать её открытой поверх готового к работе приложения значит требовать ещё
  // одно действие ровно после того, как человек сделал то, о чём просили.
  useEffect(() => {
    if (botStarted) setBotStartOpen(false);
  }, [botStarted]);

  // Право писать в личку просим сами, на входе: без него фильм человеку не отправить.
  useWriteAccessPrompt(phase === "ready" && !botStarted, setAuth);

  // Запоминаем экран (вкладка + открытая карточка) — чтобы вернуть его при заходе в
  // ближайший час. Пишем на каждое изменение: заход можно и не «закрыть» по-человечески.
  useEffect(() => {
    if (phase !== "ready") return;
    saveLastPage({ tab, movieId: selected?.id ?? null });
  }, [phase, tab, selected]);

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
    {/* Вёрстка рисовалась под телефон и «резиновая» на всю ширину: в Telegram Desktop,
        особенно в полноэкранном режиме, экран расползался на 1400+ px — три колонки
        каталога превращались в постеры в пол-экрана, а hero — в пустую широкую полосу.
        Колонка ограничена и центрирована: пропорции те же, что на телефоне, а лишнюю
        ширину разбирают брейкпоинты внутри (сетки дают больше колонок, hero — крупнее
        постер и заголовок). */}
    <div className="mx-auto min-h-screen w-full max-w-[1024px] bg-bg pb-[calc(72px+var(--safe-bottom))]">
      <TopBar status={status} onProfile={() => setProfileOpen(true)} />

      {phase === "ready" && tab === "home" && (
        <SearchBar value={search.query} onChange={search.setQuery} />
      )}
      {phase === "ready" && tab === "home" && status === "pending_review" && <StatusBanner />}

      {phase === "loading" && <HomeSkeleton />}
      {phase === "error" && <LoadError onRetry={reload} />}
      {phase === "no_telegram" && <NotInTelegram />}
      {phase === "session_expired" && <SessionExpired />}

      {phase === "ready" &&
        tab === "home" &&
        // Сбой поиска тоже открывает панель: на нём `results` = null, и без этого
        // условия юзер вместо объяснения увидел бы главную с полками — как будто поиск
        // и не запускался.
        (search.results !== null || search.failed ? (
          <SearchResults
            query={search.query}
            results={search.results ?? []}
            searching={search.searching}
            failed={search.failed}
            onRetry={search.retry}
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
      <div className="grid grid-cols-3 gap-3 px-4 pt-4 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6">
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
    <div className="grid grid-cols-3 gap-3 px-4 pt-4 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6">
      {results.map((movie) => (
        <PosterCard key={movie.id} movie={movie} onSelect={onSelect} inShelf={false} />
      ))}
    </div>
  );
}
