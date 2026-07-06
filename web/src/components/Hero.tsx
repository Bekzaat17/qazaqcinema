// Hero-баннер главного экрана: одна курируемая новинка крупно. Если у фильма есть
// горизонтальный баннер (hero_image_url, 3:2 — грузится в /add), показываем его во всю
// ширину; иначе фолбэк — портретный постер как кинематографичный фон с градиентом.

import { Play } from "lucide-react";

import type { Movie } from "../lib/api";
import { categoryLabel } from "../lib/catalog";
import { haptic } from "../lib/telegram";
import RatingPill from "./RatingPill";

export default function Hero({ movie, onSelect }: { movie: Movie; onSelect: (m: Movie) => void }) {
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

      <div className="absolute inset-x-0 bottom-0 flex flex-col items-start gap-3 p-5">
        <span className="rounded-full border border-white/15 bg-white/10 px-2.5 py-1 text-xs font-semibold text-white/90 backdrop-blur-sm">
          {categoryLabel(movie.category)}
        </span>
        <h1 className="text-3xl font-extrabold leading-[1.05] tracking-tight text-white drop-shadow-lg">
          {movie.title_kk}
        </h1>
        {movie.title_original && (
          <p className="-mt-1 text-sm text-white/60">{movie.title_original}</p>
        )}
        <div className="flex items-center gap-3 text-sm text-white/80">
          {movie.rating != null && <RatingPill rating={movie.rating} />}
          {movie.year != null && <span className="tabular">{movie.year}</span>}
        </div>
        <span className="mt-1 inline-flex items-center gap-2 rounded-2xl bg-brand px-6 py-3 text-[15px] font-semibold text-white shadow-lg shadow-brand/30">
          <Play size={18} className="fill-white" />
          Көру
        </span>
      </div>
    </button>
  );
}
