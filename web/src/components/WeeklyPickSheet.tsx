// Подтверждение недельного выбора — то, что человек видит ВМЕСТО пэйволла, пока выбор
// этой недели свободен.
//
// Смысл экрана: показать ценность до просьбы о деньгах. Поэтому здесь нет ни цен, ни
// «потом будет платно» — только предложение и одна кнопка. Разговор об оплате начинается
// на СЛЕДУЮЩЕМ фильме, когда человек уже посмотрел кино целиком.
//
// Подтверждение обязательно: выбор один на неделю, и случайный тап стоит человеку семи
// дней. Поэтому тут же названы обе границы — до какого числа смотреть и что это раз в
// неделю. Формулировка «қарай аласыз», а не «жібереміз»: видео из чата уборка сносит
// через ~40 ч, а право живёт до понедельника — обещать файл значило бы обмануть.

import { CalendarCheck, Ticket } from "lucide-react";

import type { Movie } from "../lib/api";
import { untilLabel } from "../lib/week";
import Button from "../ui/Button";
import Sheet from "../ui/Sheet";

interface WeeklyPickSheetProps {
  open: boolean;
  movie: Movie | null;
  /** Когда закрывается окно (ISO) — показываем дату, а не «7 күн»: окно общее для всех. */
  endsAt: string | null;
  busy: boolean;
  onAccept: (movie: Movie) => void;
  onClose: () => void;
}

export default function WeeklyPickSheet({
  open,
  movie,
  endsAt,
  busy,
  onAccept,
  onClose,
}: WeeklyPickSheetProps) {
  if (!open || !movie) return null;
  const until = untilLabel(endsAt);

  return (
    <Sheet open onClose={onClose} labelledBy="weekly-title">
      <div className="px-5 pb-4 pt-1 text-center">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-brand/15">
          <Ticket size={30} className="text-brand" />
        </div>
        <h2 id="weekly-title" className="text-xl font-extrabold tracking-tight text-text">
          Апталық таңдауыңыз
        </h2>
        <p className="mt-2 text-[15px] leading-relaxed text-muted">
          Осы фильмді апта соңына дейін қалағаныңызша қарай аласыз. Төлем қажет емес.
        </p>

        <div className="mt-4 flex items-center gap-3 rounded-2xl border border-border bg-elevated p-3 text-left">
          <img
            src={movie.poster_url}
            alt={movie.title_kk}
            className="h-[72px] w-12 shrink-0 rounded-xl object-cover ring-1 ring-white/10"
          />
          <div className="min-w-0">
            <p className="truncate text-[15px] font-semibold text-text">{movie.title_kk}</p>
            {movie.year != null && <p className="mt-0.5 text-xs text-faint tabular">{movie.year}</p>}
          </div>
        </div>

        {until && (
          <p className="mt-3 flex items-center justify-center gap-1.5 text-[13px] text-faint">
            <CalendarCheck size={14} className="shrink-0" />
            {until} дейін · аптасына бір фильм
          </p>
        )}

        <div className="mt-5">
          <Button loading={busy} onClick={() => onAccept(movie)}>
            <Ticket size={18} />
            Таңдауыма алу
          </Button>
          <Button variant="ghost" onClick={onClose} className="mt-1">
            Кейінірек
          </Button>
        </div>
      </div>
    </Sheet>
  );
}
