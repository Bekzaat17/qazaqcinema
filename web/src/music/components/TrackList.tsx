// Список треков. `queue` — тап по треку отправляет его и всё, что после него («играть
// отсюда»): так плейлист слушают по порядку одним нажатием. Без `queue` — один трек.

import { SEND_MAX, type Track } from "../api";
import { fromHere, moved } from "../format";
import TrackRow from "./TrackRow";

interface TrackListProps {
  tracks: Track[];
  numbered?: boolean;
  queue?: boolean;
  busy: boolean;
  onSend: (tracks: Track[]) => void;
  onMore: (track: Track) => void;
  /** Режим «Реттеу»: новый порядок отдаётся наверх, сохраняет родитель. */
  onReorder?: (tracks: Track[]) => void;
}

export default function TrackList({ tracks, numbered = false, queue = false, busy, onSend, onMore, onReorder }: TrackListProps) {
  return (
    <div className="flex flex-col">
      {tracks.map((track, index) => (
        <TrackRow
          key={track.id}
          track={track}
          position={numbered ? index + 1 : undefined}
          busy={busy}
          onPlay={() => onSend(queue ? fromHere(tracks, index, SEND_MAX) : [track])}
          onMore={() => onMore(track)}
          onMove={onReorder ? (step) => onReorder(moved(tracks, index, step)) : undefined}
          first={index === 0}
          last={index === tracks.length - 1}
        />
      ))}
    </div>
  );
}
