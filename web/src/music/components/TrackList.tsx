// Список треков: играет весь список как очередь, начиная с нажатого.

import type { Track } from "../api";
import { usePlayer } from "../usePlayer";
import TrackRow from "./TrackRow";

interface TrackListProps {
  tracks: Track[];
  numbered?: boolean;
  onMore: (track: Track) => void;
}

export default function TrackList({ tracks, numbered = false, onMore }: TrackListProps) {
  const player = usePlayer();
  return (
    <div className="flex flex-col">
      {tracks.map((track, index) => (
        <TrackRow
          key={track.id}
          track={track}
          position={numbered ? index + 1 : undefined}
          onPlay={() => player.play(tracks, index)}
          onMore={() => onMore(track)}
        />
      ))}
    </div>
  );
}
