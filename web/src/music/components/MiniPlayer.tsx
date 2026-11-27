// Мини-плеер над таб-баром: что играет, пауза, следующий. Тап открывает полный плеер.

import { Loader2, Pause, Play, SkipForward } from "../../ui-kit/adapters/icons";

import { haptic } from "../../lib/telegram";
import { usePlayer } from "../usePlayer";
import Cover from "./Cover";

export default function MiniPlayer({ onOpen }: { onOpen: () => void }) {
  const player = usePlayer();
  const track = player.current;
  if (!track) return null;
  const fill = player.duration > 0 ? (player.position / player.duration) * 100 : 0;
  return (
    <div className="fixed inset-x-0 bottom-[calc(60px+var(--safe-bottom))] z-[36] mx-auto max-w-[1024px] px-2">
      <div className="anim-pop overflow-hidden rounded-2xl border border-white/10 bg-elevated/95 shadow-[0_8px_30px_rgba(0,0,0,0.5)] backdrop-blur-xl">
        <div className="flex items-center gap-3 p-2">
          <button onClick={onOpen} className="flex min-w-0 flex-1 items-center gap-3 text-left" aria-label="Ойнатқышты ашу">
            <Cover title={track.title} performer={track.performer} url={track.cover_url} className="h-11 w-11" rounded="rounded-lg" />
            <div className="min-w-0">
              <p className="truncate text-[14px] font-semibold text-text">{track.title}</p>
              <p className="truncate text-[12px] text-muted">
                {player.unavailable ? "Тек Telegram-да тыңдауға болады" : track.performer}
              </p>
            </div>
          </button>
          <button
            onClick={() => {
              haptic.light();
              if (player.unavailable) onOpen();
              else player.toggle();
            }}
            aria-label={player.playing ? "Кідірту" : "Ойнату"}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-black active:scale-95"
          >
            {player.loading ? <Loader2 size={18} className="ui-spinner" /> : player.playing ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" className="ml-0.5" />}
          </button>
          <button onClick={() => { haptic.light(); player.next(); }} aria-label="Келесі" className="p-2 text-text active:scale-95">
            <SkipForward size={20} fill="currentColor" />
          </button>
        </div>
        <div className="h-[2px] bg-white/10">
          <div className="qm-gradient h-full transition-[width] duration-300" style={{ width: `${fill}%` }} />
        </div>
      </div>
    </div>
  );
}
