// Карточка фильма (bottom sheet): постер + метаданные + крупная «Көру».
// Гейт подписки — замок на кнопке (подсказка по has_access), но настоящий гейт — на сервере
// (App: если доступа нет → пэйволл; есть → POST /play → хэндофф-модалка).

import { Lock, Play, ShieldCheck } from "lucide-react";

import type { Movie, UserStatus } from "../lib/api";
import { categoryLabel } from "../lib/catalog";
import Button from "../ui/Button";
import Sheet from "../ui/Sheet";
import RatingPill from "./RatingPill";

interface MovieSheetProps {
  movie: Movie | null;
  hasAccess: boolean;
  status: UserStatus;
  busy: boolean;
  onWatch: (movie: Movie) => void;
  onClose: () => void;
}

export default function MovieSheet({ movie, hasAccess, status, busy, onWatch, onClose }: MovieSheetProps) {
  if (!movie) return null;
  const pending = status === "pending_review";

  return (
    <Sheet open onClose={onClose} labelledBy="movie-title">
      <div className="px-5 pb-3 pt-1">
        <div className="flex gap-4">
          <img
            src={movie.poster_url}
            alt={movie.title_kk}
            className="h-40 w-[110px] shrink-0 rounded-[var(--radius-card)] object-cover ring-1 ring-white/10"
          />
          <div className="min-w-0 flex-1 pt-1">
            <span className="rounded-full border border-border bg-elevated px-2.5 py-1 text-xs font-medium text-muted">
              {categoryLabel(movie.category)}
            </span>
            <h2 id="movie-title" className="mt-2 text-xl font-extrabold leading-tight tracking-tight text-text">
              {movie.title_kk}
            </h2>
            {movie.title_original && <p className="mt-0.5 text-sm text-faint">{movie.title_original}</p>}
            <div className="mt-2.5 flex flex-wrap items-center gap-2.5 text-sm text-muted">
              {movie.rating != null && <RatingPill rating={movie.rating} />}
              {movie.year != null && <span className="tabular">{movie.year}</span>}
            </div>
          </div>
        </div>

        {movie.description && (
          <p className="mt-4 text-[15px] leading-relaxed text-muted">{movie.description}</p>
        )}

        <div className="mt-5">
          {pending ? (
            <Button variant="surface" disabled>
              Чек тексерілуде…
            </Button>
          ) : (
            <Button loading={busy} onClick={() => onWatch(movie)}>
              {hasAccess ? <Play size={18} className="fill-white" /> : <Lock size={17} />}
              Көру
            </Button>
          )}
          <p className="mt-2.5 flex items-center justify-center gap-1.5 text-xs text-faint">
            <ShieldCheck size={13} />
            Видео ботпен чатқа жіберіледі
          </p>
        </div>
      </div>
    </Sheet>
  );
}
