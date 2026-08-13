// Hero-баннер главного экрана: одна курируемая новинка крупно. Если у фильма есть
// горизонтальный баннер (hero_image_url, 3:2 — грузится в /add), показываем его во всю
// ширину; иначе фолбэк — портретный постер как кинематографичный фон с градиентом.

import { useCallback, useEffect, useLayoutEffect, useRef } from "react";
import { Play } from "lucide-react";

import type { Movie } from "../lib/api";
import { categoryLabel } from "../lib/catalog";
import { haptic } from "../lib/telegram";
import RatingPill from "./RatingPill";

// Название hero — ВСЕГДА одной строкой. Базовый кегль TITLE_MAX_PX; если строка шире
// доступной ширины, ужимаем шрифт пропорционально (ширина текста ~линейна по font-size),
// но не мельче TITLE_MIN_PX. Обрезки многоточием нет — длинное имя читается целиком,
// просто мельче. Меняются только эти две константы.
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

export default function Hero({ movie, onSelect }: { movie: Movie; onSelect: (m: Movie) => void }) {
  const titleRef = useFitTitle(movie.title_kk);

  return (
    <button
      onClick={() => {
        haptic.light();
        onSelect(movie);
      }}
      className={`relative block ${
        movie.hero_image_url ? "aspect-[3/2]" : "aspect-[3/4]"
      } max-h-[560px] w-full overflow-hidden text-left`}
    >
      <img
        src={movie.hero_image_url ?? movie.poster_url}
        alt={movie.title_kk}
        className="h-full w-full object-cover object-center"
      />
      {/* Смешиваем низ постера с фоном страницы */}
      <div className="absolute inset-0 bg-gradient-to-t from-bg via-bg/40 to-transparent" />
      {/* ...и верх — тем же фоном, чтобы поиск и баннер не «слипались» краем */}
      <div className="absolute inset-x-0 top-0 h-28 bg-gradient-to-b from-bg via-bg/40 to-transparent" />

      <div className="absolute inset-x-0 bottom-0 flex flex-col items-start gap-2 p-4">
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
        {/* Категории — каждая отдельным чипом со своей обводкой, рядом с кнопкой */}
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
        <span className="mt-0.5 inline-flex items-center gap-2 rounded-2xl bg-brand px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-brand/30">
          <Play size={16} className="fill-white" />
          Көру
        </span>
      </div>
    </button>
  );
}
