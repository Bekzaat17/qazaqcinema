// Приглашение к подарочному первому фильму — то, что человек видит ВМЕСТО пэйволла,
// пока подарок цел.
//
// Смысл экрана: показать ценность до просьбы о деньгах. Поэтому здесь нет ни цен, ни
// «потом будет платно», ни таймеров — только предложение и одна кнопка. Разговор об
// оплате начинается на СЛЕДУЮЩЕМ фильме, когда человек уже посмотрел кино целиком.
//
// Фильм выбирает сам пользователь (мы открываем эту шторку на той карточке, которую он
// уже ткнул) — подарок, который выбрал ты сам, ценится выше навязанного.

import { Gift } from "lucide-react";

import type { Movie } from "../lib/api";
import Button from "../ui/Button";
import Sheet from "../ui/Sheet";

interface GiftSheetProps {
  open: boolean;
  movie: Movie | null;
  busy: boolean;
  onAccept: (movie: Movie) => void;
  onClose: () => void;
}

export default function GiftSheet({ open, movie, busy, onAccept, onClose }: GiftSheetProps) {
  if (!open || !movie) return null;

  return (
    <Sheet open onClose={onClose} labelledBy="gift-title">
      <div className="px-5 pb-4 pt-1 text-center">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-brand/15">
          <Gift size={30} className="text-brand" />
        </div>
        <h2 id="gift-title" className="text-xl font-extrabold tracking-tight text-text">
          Бірінші фильм — біздің сыйлық
        </h2>
        <p className="mt-2 text-[15px] leading-relaxed text-muted">
          Таңдаған фильміңізді толық көріңіз. Төлем қажет емес.
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

        <div className="mt-5">
          <Button loading={busy} onClick={() => onAccept(movie)}>
            <Gift size={18} />
            Тегін көру
          </Button>
          <Button variant="ghost" onClick={onClose} className="mt-1">
            Кейінірек
          </Button>
        </div>
      </div>
    </Sheet>
  );
}
