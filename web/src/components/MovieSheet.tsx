// Карточка фильма (bottom sheet): постер + метаданные + крупная «Көру».
// Гейт подписки — замок на кнопке (подсказка по has_access), но настоящий гейт — на сервере
// (App: если доступа нет → пэйволл; есть → POST /play → хэндофф-модалка).

import { Gift, Lock, Play, ShieldCheck, Ticket } from "lucide-react";

import type { Movie, UserStatus } from "../lib/api";
import { categoryLabel } from "../lib/catalog";
import { thumbUrl } from "../lib/poster";
import { weekLeftLabel } from "../lib/week";
import Button from "../ui/Button";
import Sheet from "../ui/Sheet";
import FavoriteButton from "./FavoriteButton";
import RatingPill from "./RatingPill";

interface MovieSheetProps {
  movie: Movie | null;
  hasAccess: boolean;
  status: UserStatus;
  busy: boolean;
  /** Недельный выбор свободен → зовём смотреть бесплатно, а не показываем замок. */
  weeklyPickAvailable: boolean;
  /** Это и есть выбор ТЕКУЩЕЙ недели → открыт до понедельника без подписки. */
  weeklyPicked: boolean;
  /** Фильм, подаренный прошлой одноразовой механикой → открыт навсегда. */
  legacyGifted: boolean;
  /** Когда закрывается недельное окно (ISO) — для счётчика «3 күн қалды». */
  weekEndsAt: string | null;
  /** Это сегодняшний бесплатный фильм дня (hero главной) — замка и пэйволла тут нет. */
  freeToday: boolean;
  onWatch: (movie: Movie) => void;
  onClose: () => void;
}

export default function MovieSheet({
  movie,
  hasAccess,
  status,
  busy,
  weeklyPickAvailable,
  weeklyPicked,
  legacyGifted,
  weekEndsAt,
  freeToday,
  onWatch,
  onClose,
}: MovieSheetProps) {
  if (!movie) return null;
  const pending = status === "pending_review";
  // Замок — только там, где смотреть действительно нельзя. У человека со свободным
  // недельным выбором или на своём фильме замок был бы враньём и гасил бы всю воронку.
  const unlocked = hasAccess || freeToday || weeklyPicked || legacyGifted || weeklyPickAvailable;
  // Ни одна подсказка этой механики не показывается подписчику: у него нет ни выбора, ни
  // счётчика, и лишняя строка на его экране — просто шум.
  const left = hasAccess ? "" : weekLeftLabel(weekEndsAt);

  return (
    <Sheet open onClose={onClose} labelledBy="movie-title">
      <div className="px-5 pb-3 pt-1">
        <div className="flex gap-4">
          <img
            src={thumbUrl(movie.poster_url)}
            decoding="async"
            alt={movie.title_kk}
            className="h-40 w-[110px] shrink-0 rounded-[var(--radius-card)] object-cover ring-1 ring-white/10"
          />
          <div className="min-w-0 flex-1 pt-1">
            <div className="flex flex-wrap gap-1.5">
              {movie.categories.map((slug) => (
                <span
                  key={slug}
                  className="rounded-full border border-border bg-elevated px-2.5 py-1 text-xs font-medium text-muted"
                >
                  {categoryLabel(slug)}
                </span>
              ))}
            </div>
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

        {freeToday && (
          // Человек открыл карточку фильма дня из полки/поиска, а не с hero: без этой
          // строки он не догадался бы, что именно это кино сегодня ничего не стоит.
          <p className="mt-4 flex items-center gap-2 rounded-2xl border border-brand/30 bg-brand/10 px-3.5 py-2.5 text-[13px] font-medium text-brand">
            <Gift size={15} className="shrink-0" />
            Бүгінгі тегін фильм — түн ортасына дейін
          </p>
        )}

        {!freeToday && !hasAccess && weeklyPicked && (
          // Человек вернулся к своему недельному фильму (видео из чата мы сносим через
          // ~40 ч, а право живёт до понедельника). Без этой строки повторная бесплатная
          // выдача выглядела бы сбоем, а исчезнувшее видео — отъёмом.
          <p className="mt-4 flex items-center gap-2 rounded-2xl border border-brand/30 bg-brand/10 px-3.5 py-2.5 text-[13px] font-medium text-brand">
            <Ticket size={15} className="shrink-0" />
            Менің апталық таңдауым{left && ` · ${left}`}
          </p>
        )}

        {!freeToday && !hasAccess && !weeklyPicked && legacyGifted && (
          <p className="mt-4 flex items-center gap-2 rounded-2xl border border-brand/30 bg-brand/10 px-3.5 py-2.5 text-[13px] font-medium text-brand">
            <Gift size={15} className="shrink-0" />
            Сыйлық фильміңіз — әрқашан қолжетімді
          </p>
        )}

        {!freeToday && !hasAccess && !weeklyPicked && !legacyGifted && weeklyPickAvailable && (
          // Приглашение вместо замка: человек ещё не знает, что одно кино в неделю ему
          // ничего не стоит, — а узнать об этом он должен ДО того, как увидит цену.
          <p className="mt-4 flex items-center gap-2 rounded-2xl border border-brand/30 bg-brand/10 px-3.5 py-2.5 text-[13px] font-medium text-brand">
            <Ticket size={15} className="shrink-0" />
            Апталық таңдауыңыз бос — осы фильмді тегін алыңыз
          </p>
        )}

        {!freeToday && !hasAccess && !weeklyPicked && !legacyGifted && !weeklyPickAvailable && (
          // Выбор уже потрачен на другое кино. Называем срок, а не просто отказываем:
          // иначе «почему тот бесплатный, а этот нет» остаётся без ответа.
          <p className="mt-4 rounded-2xl border border-border bg-elevated px-3.5 py-2.5 text-[13px] text-muted">
            Апталық таңдауыңыз қазір басқа фильмде{left && ` · ${left}`}
          </p>
        )}

        <div className="mt-5">
          {pending ? (
            <Button variant="surface" disabled>
              Чек тексерілуде…
            </Button>
          ) : (
            <div className="flex items-stretch gap-2.5">
              <Button loading={busy} onClick={() => onWatch(movie)}>
                {unlocked ? <Play size={18} className="fill-white" /> : <Lock size={17} />}
                {freeToday || (!hasAccess && weeklyPickAvailable && !weeklyPicked && !legacyGifted)
                  ? "Тегін көру"
                  : "Көру"}
              </Button>
              <FavoriteButton movieId={movie.id} variant="inline" />
            </div>
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
