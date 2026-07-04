// Постер-карточка для полки (портрет 2:3). Замок на карточке НЕ рисуем — гейт подписки
// живёт только на кнопке «Көру» (PLAN, Фаза 9).

import type { Movie } from "../lib/api";
import { haptic } from "../lib/telegram";
import RatingPill from "./RatingPill";

interface PosterCardProps {
  movie: Movie;
  onSelect: (movie: Movie) => void;
  /** В полке — фиксированная ширина; в сетке поиска — тянется по колонке. */
  inShelf?: boolean;
}

export default function PosterCard({ movie, onSelect, inShelf = true }: PosterCardProps) {
  return (
    <button
      onClick={() => {
        haptic.light();
        onSelect(movie);
      }}
      className={`group flex flex-col text-left ${
        inShelf ? "w-[132px] shrink-0 snap-start" : "w-full"
      }`}
    >
      <div className="relative aspect-[2/3] w-full overflow-hidden rounded-[var(--radius-card)] bg-surface-2 ring-1 ring-white/5 transition-transform duration-200 group-active:scale-[0.97]">
        <img
          src={movie.poster_url}
          alt={movie.title_kk}
          loading="lazy"
          className="h-full w-full object-cover"
        />
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-black/60 to-transparent" />
        {movie.rating != null && <RatingPill rating={movie.rating} className="absolute right-2 top-2" />}
      </div>
      <p className="mt-2 line-clamp-2 text-[13px] font-medium leading-tight text-text">{movie.title_kk}</p>
      {movie.year != null && <p className="mt-0.5 text-xs text-faint tabular">{movie.year}</p>}
    </button>
  );
}
