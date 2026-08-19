// Hero главного экрана = ФИЛЬМ ДНЯ (решение 2026-08-19).
//
// Раньше здесь висела просто курируемая карточка: человек жал «Көру» и упирался в
// пэйволл — лучшее место экрана ничего не обещало. Теперь оно обещает конкретное: вот
// это кино сегодня можно посмотреть бесплатно. Отсюда и состав блока: бейдж «Бүгін
// тегін», обратный отсчёт до смены и одна пульсирующая кнопка «Тегін көру».
//
// ДВА ВАРИАНТА ВЁРСТКИ, одинаковые по смыслу и почти одинаковые по высоте:
//
//   • есть широкий баннер (hero_image_url, 3:2) → кинематографичный полноэкранный кадр,
//     текст на нижнем скриме — ровно та вёрстка, что была до фильма дня (она хорошо
//     смотрелась, менять её незачем). Единственная правка — кнопка: «Тегін көру» с
//     пульсом вместо обычной «Көру». Бейджа тут нет намеренно: на широком кадре о
//     бесплатности говорит сама кнопка, а лишняя плашка спорила бы с названием.
//   • баннера нет → «афиша»: фоном идёт ТОТ ЖЕ постер, увеличенный и размытый, а поверх
//     лежит его чёткая копия 2:3. Постер 2:3 нельзя ни растянуть, ни обрезать до 3:2 —
//     кадр скомпонован вертикально, центр-кроп режет лицо и название. Зато размытая
//     копия даёт широкую поверхность в цветах самого фильма: блок каждый день выглядит
//     нарисованным под сегодняшнее кино, а нового ассета не нужно ни одного.
//
// Клик по площади открывает карточку фильма, клик по кнопке сразу шлёт видео — поэтому
// подложка это отдельная невидимая кнопка, а не обёртка (кнопка в кнопке невалидна).

import { useCallback, useEffect, useLayoutEffect, useRef } from "react";
import { Gift, Play, Timer } from "lucide-react";

import { useCountdown } from "../hooks/useCountdown";
import type { Movie } from "../lib/api";
import { categoryLabel } from "../lib/catalog";
import { haptic } from "../lib/telegram";
import RatingPill from "./RatingPill";

// Название на широком баннере — ВСЕГДА одной строкой. Базовый кегль TITLE_MAX_PX; если
// строка шире доступной ширины, ужимаем шрифт пропорционально (ширина текста ~линейна по
// font-size), но не мельче TITLE_MIN_PX. Обрезки многоточием нет — длинное имя читается
// целиком, просто мельче.
const TITLE_MAX_PX = 24;
const TITLE_MIN_PX = 14;

/** Подгоняет кегль заголовка под ширину контейнера (одна строка, без переноса). */
function useFitTitle(text: string) {
  const ref = useRef<HTMLHeadingElement>(null);

  const fit = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    el.style.fontSize = `${TITLE_MAX_PX}px`;
    const available = el.clientWidth;
    const natural = el.scrollWidth; // реальная ширина строки при базовом кегле
    if (!available || natural <= available) return;
    const px = Math.max(TITLE_MIN_PX, Math.floor((TITLE_MAX_PX * available) / natural));
    el.style.fontSize = `${px}px`;
  }, []);

  useLayoutEffect(() => {
    fit();
    // Inter подгружается асинхронно: до подмены шрифта ширина другая — меряем ещё раз.
    document.fonts?.ready.then(fit).catch(() => {});
  }, [fit, text]);

  useEffect(() => {
    const box = ref.current?.parentElement;
    if (!box || typeof ResizeObserver === "undefined") return;
    // Следим за РОДИТЕЛЕМ (его ширина не зависит от кегля) и только за шириной —
    // иначе смена font-size меняла бы высоту и наблюдатель зациклился бы сам на себе.
    let last = box.clientWidth;
    const ro = new ResizeObserver(([entry]) => {
      const width = entry.contentRect.width;
      if (width === last) return;
      last = width;
      fit();
    });
    ro.observe(box);
    return () => ro.disconnect();
  }, [fit]);

  return ref;
}

interface HeroProps {
  movie: Movie;
  /** До какого момента фильм бесплатен (ISO с бэка). null → обычная витрина без бейджа. */
  freeUntil: string | null;
  busy: boolean;
  onSelect: (movie: Movie) => void;
  onWatch: (movie: Movie) => void;
}

/** Бейдж «сегодня бесплатно» — единственное место, где мы вообще произносим слово «тегін». */
function FreeBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-brand/20 px-2.5 py-1 text-[11px] font-extrabold uppercase tracking-[0.08em] text-brand-050 ring-1 ring-inset ring-brand/40 backdrop-blur-sm">
      <Gift size={12} />
      Бүгін тегін
    </span>
  );
}

/** Сколько осталось до смены фильма дня. Без срока (обычная витрина) — ничего. */
function Countdown({ left }: { left: string | null }) {
  if (!left) return null;
  return (
    <span className="inline-flex items-center gap-1.5 text-[12px] font-medium text-white/70">
      <Timer size={13} />
      <span className="tabular">{left}</span> қалды
    </span>
  );
}

/** Главная кнопка. Пульсирует только когда кино действительно бесплатно. */
function WatchButton({
  free,
  busy,
  onClick,
}: {
  free: boolean;
  busy: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={busy}
      onClick={onClick}
      className={`pointer-events-auto inline-flex items-center justify-center gap-2 rounded-2xl bg-brand px-5 py-3 text-sm font-bold text-white shadow-lg shadow-brand/30 transition-transform duration-150 active:scale-[0.98] disabled:opacity-60 ${
        free ? "anim-pulse-ring" : ""
      }`}
    >
      <Play size={16} className="fill-white" />
      {free ? "Тегін көру" : "Көру"}
    </button>
  );
}

export default function Hero({ movie, freeUntil, busy, onSelect, onWatch }: HeroProps) {
  const left = useCountdown(freeUntil);
  const free = freeUntil !== null;

  const openCard = () => {
    haptic.light();
    onSelect(movie);
  };
  const watch = () => {
    haptic.medium();
    onWatch(movie);
  };

  return movie.hero_image_url
    ? <BannerHero {...{ movie, free, left, busy, openCard, watch }} />
    : <PosterHero {...{ movie, free, left, busy, openCard, watch }} />;
}

interface VariantProps {
  movie: Movie;
  free: boolean;
  left: string | null;
  busy: boolean;
  openCard: () => void;
  watch: () => void;
}

/** Вариант с широким баннером: кадр во всю ширину, текст на нижнем скриме. */
function BannerHero({ movie, free, left, busy, openCard, watch }: VariantProps) {
  const titleRef = useFitTitle(movie.title_kk);

  return (
    <section className="relative isolate aspect-[3/2] max-h-[560px] w-full overflow-hidden">
      <img
        src={movie.hero_image_url ?? movie.poster_url}
        alt={movie.title_kk}
        className="h-full w-full object-cover object-center"
      />
      {/* Низ смешиваем с фоном страницы, верх — чтобы поиск не слипался с картинкой краем */}
      <div className="absolute inset-0 bg-gradient-to-t from-bg via-bg/45 to-transparent" />
      <div className="absolute inset-x-0 top-0 h-28 bg-gradient-to-b from-bg via-bg/40 to-transparent" />

      <button
        type="button"
        onClick={openCard}
        aria-label={`${movie.title_kk} — толығырақ`}
        className="absolute inset-0 z-10"
      />

      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 flex flex-col items-start gap-2 p-4">
        <h1
          ref={titleRef}
          style={{ fontSize: `${TITLE_MAX_PX}px` }}
          className="w-full whitespace-nowrap font-extrabold leading-[1.1] tracking-tight text-white drop-shadow-lg"
        >
          {movie.title_kk}
        </h1>
        {movie.title_original && (
          <p className="-mt-1 w-full truncate text-xs text-white/60">{movie.title_original}</p>
        )}
        <div className="flex items-center gap-2.5 text-[13px] text-white/80">
          {movie.rating != null && <RatingPill rating={movie.rating} />}
          {movie.year != null && <span className="tabular">{movie.year}</span>}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {movie.categories.map((slug) => (
            <span
              key={slug}
              className="rounded-full border border-white/15 bg-white/10 px-2 py-0.5 text-[11px] font-semibold text-white/90 backdrop-blur-sm"
            >
              {categoryLabel(slug)}
            </span>
          ))}
        </div>
        <div className="mt-0.5 flex items-center gap-3">
          <WatchButton free={free} busy={busy} onClick={watch} />
          <Countdown left={left} />
        </div>
      </div>
    </section>
  );
}

/** Вариант «афиша»: широкой картинки нет — делаем её из постера (размытие + масштаб). */
function PosterHero({ movie, free, left, busy, openCard, watch }: VariantProps) {
  return (
    <section className="relative isolate aspect-[4/3] max-h-[420px] w-full overflow-hidden">
      {/* Подложка = тот же постер: цвета фильма, но никакой читаемой детали. `scale`
          обязателен — blur размывает и КРАЯ, без наплыва по периметру шли бы полосы. */}
      <img
        src={movie.poster_url}
        alt=""
        aria-hidden
        className="anim-breathe absolute inset-0 h-full w-full scale-[1.12] object-cover blur-2xl saturate-150"
      />
      {/* Контраст текста не зависит от того, насколько светлым оказался постер */}
      <div className="absolute inset-0 bg-bg/55" />
      {/* Низ растворяем в фоне страницы — блок переходит в полки без шва */}
      <div className="absolute inset-0 bg-gradient-to-t from-bg via-bg/35 to-transparent" />
      {/* ...и ВЕРХ тем же фоном: без этого размытая подложка обрывалась ровной линией
          под поиском — единственный жёсткий край на всём экране. */}
      <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-bg via-bg/55 to-transparent" />

      <button
        type="button"
        onClick={openCard}
        aria-label={`${movie.title_kk} — толығырақ`}
        className="absolute inset-0 z-10"
      />

      <div className="pointer-events-none relative z-20 flex h-full items-center gap-4 px-4">
        {/* Чёткий постер — «физическая» афиша на световом пятне: кольцо + глубокая тень */}
        <img
          src={movie.poster_url}
          alt={movie.title_kk}
          className="aspect-[2/3] w-[34%] max-w-[136px] shrink-0 rounded-2xl object-cover shadow-[0_16px_44px_rgb(0_0_0/0.65)] ring-1 ring-white/15"
        />
        <div className="flex min-w-0 flex-col items-start gap-2">
          {free && <FreeBadge />}
          <h1 className="line-clamp-2 text-[20px] font-extrabold leading-[1.15] tracking-tight text-white drop-shadow-lg">
            {movie.title_kk}
          </h1>
          {movie.title_original && (
            <p className="-mt-1 w-full truncate text-xs text-white/55">{movie.title_original}</p>
          )}
          <div className="flex items-center gap-2.5 text-[13px] text-white/80">
            {movie.rating != null && <RatingPill rating={movie.rating} />}
            {movie.year != null && <span className="tabular">{movie.year}</span>}
          </div>
          <WatchButton free={free} busy={busy} onClick={watch} />
          <Countdown left={left} />
        </div>
      </div>
    </section>
  );
}
