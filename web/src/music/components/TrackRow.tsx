// Строка трека. Тап — «тыңдау»: трек (или он и следующие в списке) уходит в чат с ботом.
// Сердце забирает себе, «⋯» — действия. В режиме «Реттеу» вместо них — стрелки порядка.

import { ArrowDown, ArrowUp, Heart, Loader2, MoreHorizontal, Send } from "../../ui-kit/adapters/icons";

import type { Track } from "../api";
import { duration } from "../format";
import { useLibrary } from "../useLibrary";
import Cover from "./Cover";

interface TrackRowProps {
  track: Track;
  position?: number;
  busy: boolean;
  onPlay: () => void;
  onMore: () => void;
  /** Режим «Реттеу»: стрелки вместо сердца и меню. */
  onMove?: (step: -1 | 1) => void;
  first?: boolean;
  last?: boolean;
}

export default function TrackRow({ track, position, busy, onPlay, onMore, onMove, first, last }: TrackRowProps) {
  const library = useLibrary();
  const saved = library.has(track.id);
  return (
    <div className="flex items-center gap-3 rounded-2xl px-2 py-1.5 active:bg-white/5">
      <button
        onClick={onPlay}
        disabled={busy || Boolean(onMove)}
        className="flex min-w-0 flex-1 items-center gap-3 text-left disabled:opacity-100"
        aria-label={`${track.performer} — ${track.title}: Telegram-да тыңдау`}
      >
        {position !== undefined && (
          <span className="w-5 shrink-0 text-center text-[13px] font-semibold tabular text-faint">{position}</span>
        )}
        <div className="relative">
          <Cover title={track.title} performer={track.performer} />
          {!onMove && (
            <span className="absolute -bottom-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-bg text-music">
              {busy ? <Loader2 size={11} className="ui-spinner" /> : <Send size={10} />}
            </span>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[15px] font-semibold text-text">{track.title}</p>
          <p className="truncate text-[13px] text-muted">
            {track.performer}
            <span className="text-faint"> · {duration(track.duration_sec)}</span>
          </p>
        </div>
      </button>
      {onMove ? (
        <>
          <button onClick={() => onMove(-1)} disabled={first} aria-label="Жоғары" className="rounded-full p-2 text-text disabled:opacity-25">
            <ArrowUp size={20} />
          </button>
          <button onClick={() => onMove(1)} disabled={last} aria-label="Төмен" className="-mr-1 rounded-full p-2 text-text disabled:opacity-25">
            <ArrowDown size={20} />
          </button>
        </>
      ) : (
        <>
          <button
            onClick={() => library.toggle(track.id)}
            aria-label={saved ? "Менің музыкамнан алып тастау" : "Менің музыкама қосу"}
            aria-pressed={saved}
            className={`rounded-full p-2 transition-transform active:scale-90 ${saved ? "text-music-pink" : "text-faint"}`}
          >
            <Heart size={20} fill={saved ? "currentColor" : "none"} />
          </button>
          <button onClick={onMore} aria-label="Әрекеттер" className="-mr-1 rounded-full p-2 text-faint active:text-text">
            <MoreHorizontal size={20} />
          </button>
        </>
      )}
    </div>
  );
}
