// Недельный выбор во вкладке «Таңдаулы» — витрина, а не строка в списке.
//
// Одинокий постер в сетке читался как «ещё один избранный фильм», хотя это единственное
// кино, которое человеку прямо сейчас ничего не стоит. Поэтому блок собран по образцу
// hero главной: широкая поверхность из САМОГО постера (увеличенная размытая копия под
// чёткой) плюс название, оценка, год и срок — те же элементы, что и на фильме дня, и
// узнаётся он так же с первого взгляда.
//
// Про постер 2:3 и размытую подложку — подробности в `Hero`, приём и причины те же.

import { Ticket, Timer } from "lucide-react";

import type { Movie } from "../lib/api";
import { haptic } from "../lib/telegram";
import RatingPill from "./RatingPill";

interface WeeklyPickCardProps {
  movie: Movie;
  /** «3 күн қалды» — сколько осталось до конца окна. Пусто → строки нет. */
  left: string;
  onSelect: (movie: Movie) => void;
}

export default function WeeklyPickCard({ movie, left, onSelect }: WeeklyPickCardProps) {
  return (
    <button
      type="button"
      onClick={() => {
        haptic.light();
        onSelect(movie);
      }}
      aria-label={`${movie.title_kk} — толығырақ`}
      // Высота ЯВНАЯ, без `aspect-ratio` + `max-height`: это сочетание WebKit (Mini App
      // на macOS) считает в нулевую высоту и блок исчезает — см. тот же комментарий в Hero.
      className="relative isolate flex h-[min(46vw,184px)] w-full items-center gap-4 overflow-hidden rounded-[var(--radius-card)] text-left ring-1 ring-white/10 transition-transform duration-200 active:scale-[0.99]"
    >
      <img
        src={movie.poster_url}
        alt=""
        aria-hidden
        decoding="async"
        className="absolute inset-0 h-full w-full scale-[1.12] object-cover blur-xl saturate-150"
      />
      {/* Затемняем ровно настолько, чтобы текст читался на любом постере: блок высотой
          180 px под 40-пиксельным блюром и парой плотных слоёв превращался в серый
          прямоугольник — то есть терял единственное, ради чего эта подложка тут есть. */}
      <div className="absolute inset-0 bg-bg/35" />
      <div className="absolute inset-0 bg-gradient-to-r from-bg/45 via-transparent to-bg/55" />

      <img
        src={movie.poster_url}
        alt={movie.title_kk}
        decoding="async"
        className="relative z-10 ml-3.5 aspect-[2/3] h-[82%] shrink-0 rounded-xl object-cover shadow-[0_12px_34px_rgb(0_0_0/0.6)] ring-1 ring-white/15"
      />

      <div className="relative z-10 flex min-w-0 flex-1 flex-col items-start gap-1.5 pr-4">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-brand/20 px-2.5 py-1 text-[11px] font-extrabold uppercase tracking-[0.08em] text-brand-050 ring-1 ring-inset ring-brand/40 backdrop-blur-sm">
          <Ticket size={12} />
          Апталық таңдауым
        </span>
        <h2 className="line-clamp-2 text-[17px] font-extrabold leading-[1.15] tracking-tight text-white drop-shadow-lg sm:text-xl">
          {movie.title_kk}
        </h2>
        {movie.title_original && (
          <p className="w-full truncate text-xs text-white/55">{movie.title_original}</p>
        )}
        <div className="flex items-center gap-2.5 text-[13px] text-white/80">
          {movie.rating != null && <RatingPill rating={movie.rating} />}
          {movie.year != null && <span className="tabular">{movie.year}</span>}
        </div>
        {left && (
          <span className="inline-flex items-center gap-1.5 text-[12px] font-medium text-star">
            <Timer size={13} />
            <span className="tabular">{left}</span>
          </span>
        )}
      </div>
    </button>
  );
}
