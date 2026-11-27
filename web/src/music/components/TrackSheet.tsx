// Действия с треком: в чат (фоновое прослушивание), к себе, в плейлист, поделиться.

import { Heart, Info, ListPlus, Send, Share2, Trash2, type LucideIcon } from "../../ui-kit/adapters/icons";

import Sheet from "../../ui/Sheet";
import type { Track } from "../api";
import { duration } from "../format";
import { useLibrary } from "../useLibrary";
import Cover from "./Cover";

interface TrackSheetProps {
  track: Track | null;
  onClose: () => void;
  onSend: (track: Track) => void;
  onAddToPlaylist: (track: Track) => void;
  onShare: (track: Track) => void;
  /** Страница трека: сколько слушают, похожие, плейлисты с ним. */
  onAbout: (track: Track) => void;
  /** Только в своём плейлисте: убрать трек из него. */
  onRemove?: (track: Track) => void;
}

function Action({ Icon, label, hint, onClick, tone = "text-text" }: { Icon: LucideIcon; label: string; hint?: string; onClick: () => void; tone?: string }) {
  return (
    <button onClick={onClick} className="flex w-full items-center gap-4 rounded-2xl px-3 py-3 text-left active:bg-white/5">
      <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-elevated ${tone}`}>
        <Icon size={19} />
      </span>
      <span className="min-w-0">
        <span className={`block text-[15px] font-semibold ${tone}`}>{label}</span>
        {hint && <span className="block text-[12px] text-faint">{hint}</span>}
      </span>
    </button>
  );
}

export default function TrackSheet({ track, onClose, onSend, onAddToPlaylist, onShare, onAbout, onRemove }: TrackSheetProps) {
  const library = useLibrary();
  if (!track) return null;
  const saved = library.has(track.id);
  const run = (action: (t: Track) => void) => () => {
    onClose();
    action(track);
  };
  return (
    <Sheet open onClose={onClose} labelledBy="track-sheet-title">
      <div className="px-4 pb-2">
        <div className="mb-3 flex items-center gap-3 px-1">
          <Cover title={track.title} performer={track.performer} className="h-14 w-14" />
          <div className="min-w-0">
            <h2 id="track-sheet-title" className="truncate text-[16px] font-bold text-text">{track.title}</h2>
            <p className="truncate text-[13px] text-muted">{track.performer} · {duration(track.duration_sec)}</p>
          </div>
        </div>
        <Action Icon={Send} label="Telegram-да тыңдау" hint="Ән чатқа келеді — экран сөнсе де ойнайды" onClick={run(onSend)} tone="text-music" />
        <Action
          Icon={Heart}
          label={saved ? "Менің музыкамнан алып тастау" : "Менің музыкама қосу"}
          onClick={() => { library.toggle(track.id); onClose(); }}
        />
        <Action Icon={ListPlus} label="Плейлистке қосу" onClick={run(onAddToPlaylist)} />
        <Action Icon={Info} label="Ән туралы" hint="Кім тыңдайды, ұқсас әндер, плейлистер" onClick={run(onAbout)} />
        <Action Icon={Share2} label="Досқа бөлісу" onClick={run(onShare)} />
        {onRemove && <Action Icon={Trash2} label="Плейлисттен алып тастау" onClick={run(onRemove)} tone="text-[#ff7770]" />}
      </div>
    </Sheet>
  );
}
