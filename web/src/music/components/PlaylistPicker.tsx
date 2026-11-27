// Выбор плейлиста для трека. Первая строка — новый плейлист: трек сразу ляжет в него.

import { useEffect, useState } from "react";

import { Loader2, Plus } from "../../ui-kit/adapters/icons";

import Sheet from "../../ui/Sheet";
import { musicApi, type Playlist, type Track } from "../api";
import { tracksLabel } from "../format";
import PlaylistCover from "./PlaylistCover";

interface PlaylistPickerProps {
  track: Track | null;
  onClose: () => void;
  onPick: (playlist: Playlist, track: Track) => void;
  onCreate: (track: Track) => void;
}

export default function PlaylistPicker({ track, onClose, onPick, onCreate }: PlaylistPickerProps) {
  const [playlists, setPlaylists] = useState<Playlist[] | null>(null);

  useEffect(() => {
    if (!track) return;
    setPlaylists(null);
    musicApi.playlists().then(setPlaylists, () => setPlaylists([]));
  }, [track]);

  if (!track) return null;
  return (
    <Sheet open onClose={onClose} labelledBy="picker-title">
      <div className="px-4 pb-2">
        <h2 id="picker-title" className="px-1 pb-3 text-lg font-extrabold tracking-tight text-text">Плейлистке қосу</h2>
        <button onClick={() => onCreate(track)} className="flex w-full items-center gap-3 rounded-2xl px-1 py-2 text-left active:bg-white/5">
          <span className="qm-gradient flex h-12 w-12 items-center justify-center rounded-xl text-white">
            <Plus size={24} />
          </span>
          <span className="text-[15px] font-semibold text-text">Жаңа плейлист</span>
        </button>
        {playlists === null ? (
          <div className="flex justify-center py-6 text-muted"><Loader2 className="ui-spinner" /></div>
        ) : (
          playlists.map((playlist) => (
            <button
              key={playlist.id}
              onClick={() => onPick(playlist, track)}
              className="flex w-full items-center gap-3 rounded-2xl px-1 py-2 text-left active:bg-white/5"
            >
              <span className="h-12 w-12 overflow-hidden rounded-xl">
                <PlaylistCover covers={playlist.covers} seed={playlist.title} />
              </span>
              <span className="min-w-0">
                <span className="block truncate text-[15px] font-semibold text-text">{playlist.title}</span>
                <span className="block text-[12px] text-faint">{tracksLabel(playlist.track_count)}</span>
              </span>
            </button>
          ))
        )}
      </div>
    </Sheet>
  );
}
