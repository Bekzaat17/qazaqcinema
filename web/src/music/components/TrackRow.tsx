// Строка трека — основной кирпич раздела. Тап по строке играет, сердце забирает себе,
// «⋯» открывает действия (в чат, в плейлист, поделиться).

import { Heart, MoreHorizontal } from "../../ui-kit/adapters/icons";

import type { Track } from "../api";
import { duration } from "../format";
import { useLibrary } from "../useLibrary";
import { usePlayer } from "../usePlayer";
import Cover from "./Cover";
import Equalizer from "./Equalizer";

interface TrackRowProps {
  track: Track;
  position?: number;
  onPlay: () => void;
  onMore: () => void;
}

export default function TrackRow({ track, position, onPlay, onMore }: TrackRowProps) {
  const { current, playing } = usePlayer();
  const library = useLibrary();
  const isCurrent = current?.id === track.id;
  const saved = library.has(track.id);
  return (
    <div className={`group flex items-center gap-3 rounded-2xl px-2 py-1.5 transition-colors ${isCurrent ? "bg-music/10" : "active:bg-white/5"}`}>
      <button onClick={onPlay} className="flex min-w-0 flex-1 items-center gap-3 text-left" aria-label={`${track.performer} — ${track.title}`}>
        {position !== undefined && (
          <span className="w-5 shrink-0 text-center text-[13px] font-semibold tabular text-faint">
            {isCurrent ? <Equalizer paused={!playing} /> : position}
          </span>
        )}
        <div className="relative">
          <Cover title={track.title} performer={track.performer} url={track.cover_url} />
          {isCurrent && position === undefined && (
            <span className="absolute inset-0 flex items-center justify-center rounded-xl bg-black/45">
              <Equalizer paused={!playing} />
            </span>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className={`truncate text-[15px] font-semibold ${isCurrent ? "text-music" : "text-text"}`}>{track.title}</p>
          <p className="truncate text-[13px] text-muted">
            {track.performer}
            <span className="text-faint"> · {duration(track.duration_sec)}</span>
          </p>
        </div>
      </button>
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
    </div>
  );
}
