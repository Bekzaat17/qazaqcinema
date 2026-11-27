// «Менің музыкам»: сохранённые треки и свои плейлисты.

import { useCallback, useEffect, useState } from "react";

import { Heart, Loader2, Play, Plus } from "../ui-kit/adapters/icons";

import { musicApi, SEND_MAX, type Playlist, type Track } from "./api";
import PlaylistCover from "./components/PlaylistCover";
import TrackList from "./components/TrackList";
import { tracksLabel } from "./format";
import { useLibrary } from "./useLibrary";

type Segment = "tracks" | "playlists";

interface LibraryViewProps {
  onMore: (track: Track) => void;
  onOpenPlaylist: (playlist: Playlist) => void;
  onCreatePlaylist: () => void;
  onSend: (tracks: Track[]) => void;
  busy: boolean;
  playlistsVersion: number;
  onBrowse: () => void;
}

export default function LibraryView({ onMore, onOpenPlaylist, onCreatePlaylist, onSend, busy, playlistsVersion, onBrowse }: LibraryViewProps) {
  const [segment, setSegment] = useState<Segment>("tracks");
  const [tracks, setTracks] = useState<Track[] | null>(null);
  const [playlists, setPlaylists] = useState<Playlist[] | null>(null);
  const library = useLibrary();

  const loadTracks = useCallback(() => {
    musicApi.library().then(setTracks, () => setTracks((prev) => prev ?? []));
  }, []);

  useEffect(loadTracks, [loadTracks, library.version]);
  useEffect(() => {
    musicApi.playlists().then(setPlaylists, () => setPlaylists((prev) => prev ?? []));
  }, [playlistsVersion]);

  return (
    <div className="pb-6">
      <div className="px-4 pt-4">
        <h1 className="text-[26px] font-extrabold tracking-tight text-text">Менің музыкам</h1>
        <div className="mt-3 inline-flex rounded-full bg-surface p-1" role="tablist">
          {(["tracks", "playlists"] as const).map((key) => (
            <button
              key={key}
              role="tab"
              aria-selected={segment === key}
              onClick={() => setSegment(key)}
              className={`rounded-full px-4 py-1.5 text-[14px] font-semibold transition-colors ${segment === key ? "bg-white text-black" : "text-muted"}`}
            >
              {key === "tracks" ? "Әндер" : "Плейлистер"}
            </button>
          ))}
        </div>
      </div>

      {segment === "tracks" ? (
        tracks === null ? (
          <div className="flex justify-center py-12 text-muted"><Loader2 className="ui-spinner" /></div>
        ) : tracks.length === 0 ? (
          <div className="px-8 py-12 text-center">
            <Heart size={36} className="mx-auto text-music-pink" />
            <p className="mt-3 text-[15px] font-semibold text-text">Мұнда әзірге бос</p>
            <p className="mt-1 text-[13px] leading-relaxed text-muted">Ұнаған әннің жанындағы ♡ белгісін басыңыз — ол осында сақталады.</p>
            <button onClick={onBrowse} className="mt-4 rounded-full bg-elevated px-5 py-2.5 text-[14px] font-semibold text-text">Ән іздеу</button>
          </div>
        ) : (
          <>
            <div className="px-4 pb-2 pt-4">
              <button
                onClick={() => onSend(tracks.slice(0, SEND_MAX))}
                disabled={busy}
                className="qm-gradient flex w-full items-center justify-center gap-2 rounded-2xl py-3 text-[15px] font-bold text-white active:scale-[0.98] disabled:opacity-60"
              >
                {busy ? <Loader2 size={18} className="ui-spinner" /> : <Play size={18} fill="currentColor" />} Бәрін ойнату
              </button>
              <p className="mt-2 text-center text-[12px] text-faint">
                Әндер чатқа ретімен келеді — Telegram оларды бірінен соң бірін ойнатады.
              </p>
            </div>
            <p className="px-4 pb-1 text-[12px] text-faint">{tracksLabel(tracks.length)}</p>
            <div className="px-2"><TrackList tracks={tracks} queue busy={busy} onSend={onSend} onMore={onMore} /></div>
          </>
        )
      ) : playlists === null ? (
        <div className="flex justify-center py-12 text-muted"><Loader2 className="ui-spinner" /></div>
      ) : (
        <div className="grid grid-cols-2 gap-3 px-4 pt-4 sm:grid-cols-3">
          <button onClick={onCreatePlaylist} className="flex aspect-square flex-col items-center justify-center gap-2 rounded-3xl border border-dashed border-white/15 bg-surface text-muted active:bg-elevated">
            <span className="qm-gradient flex h-12 w-12 items-center justify-center rounded-full text-white"><Plus size={24} /></span>
            <span className="text-[14px] font-semibold">Жаңа плейлист</span>
          </button>
          {playlists.map((playlist) => (
            <button key={playlist.id} onClick={() => onOpenPlaylist(playlist)} className="text-left active:scale-[0.98]">
              <div className="aspect-square overflow-hidden rounded-3xl shadow-[0_8px_24px_rgba(0,0,0,0.35)]">
                <PlaylistCover seed={playlist.title} />
              </div>
              <p className="mt-2 truncate text-[14px] font-semibold text-text">{playlist.title}</p>
              <p className="text-[12px] text-faint">
                {tracksLabel(playlist.track_count)}
                {playlist.is_public && " · бәріне ашық"}
              </p>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
