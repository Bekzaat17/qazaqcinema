// Экран плейлиста — свой или чужой (открыт по ссылке). Свой можно переименовать,
// удалить и чистить; чужой — сохранить себе копией. Оба — слушать и отправить в чат.

import type { ReactNode } from "react";

import { ArrowLeft, Bookmark, Loader2, Pencil, Play, Send, Share2, Shuffle, Trash2 } from "../ui-kit/adapters/icons";

import type { PlaylistDetail, Track } from "./api";
import PlaylistCover from "./components/PlaylistCover";
import TrackList from "./components/TrackList";
import { duration, shuffled, tracksLabel } from "./format";
import { usePlayer } from "./usePlayer";

interface PlaylistScreenProps {
  playlist: PlaylistDetail | null;
  failed: boolean;
  sending: boolean;
  saving: boolean;
  onBack: () => void;
  onMore: (track: Track) => void;
  onSend: () => void;
  onShare: () => void;
  onRename: () => void;
  onDelete: () => void;
  onSave: () => void;
}

export default function PlaylistScreen(props: PlaylistScreenProps) {
  const { playlist, failed, sending, saving, onBack, onMore, onSend, onShare, onRename, onDelete, onSave } = props;
  const player = usePlayer();
  const total = playlist?.tracks.reduce((sum, track) => sum + track.duration_sec, 0) ?? 0;

  return (
    <div className="anim-fade fixed inset-0 z-[35] overflow-y-auto bg-bg pb-[calc(150px+var(--safe-bottom))]">
      <div className="relative">
        {/* Фон шапки — та же обложка, размытая и обрезанная по своему блоку: без
            overflow-hidden размытие вылезает за градиент резкой полосой. */}
        <div className="pointer-events-none absolute inset-x-0 top-0 h-96 overflow-hidden" aria-hidden="true">
          <div className="h-full w-full scale-150 opacity-45 blur-3xl">
            {playlist && <PlaylistCover covers={playlist.covers} seed={playlist.title} />}
          </div>
          <div className="absolute inset-0 bg-gradient-to-b from-transparent via-bg/60 to-bg" />
        </div>
        <div className="relative mx-auto max-w-[1024px] px-4 pt-[calc(12px+var(--safe-top))]">
          <button onClick={onBack} aria-label="Артқа" className="-ml-2 rounded-full p-2 text-text active:bg-white/10">
            <ArrowLeft size={24} />
          </button>
          {!playlist ? (
            <div className="flex justify-center py-24 text-muted">
              {failed ? <p className="text-[15px]">Плейлист табылмады.</p> : <Loader2 className="ui-spinner" />}
            </div>
          ) : (
            <>
              <div className="mx-auto mt-2 aspect-square w-52 overflow-hidden rounded-[28px] shadow-[0_20px_50px_rgba(0,0,0,0.5)]">
                <PlaylistCover covers={playlist.covers} seed={playlist.title} />
              </div>
              <h1 className="mt-5 text-center text-[24px] font-extrabold tracking-tight text-text">{playlist.title}</h1>
              <p className="mt-1 text-center text-[13px] text-muted">
                {tracksLabel(playlist.track_count)}
                {total > 0 && ` · ${duration(total)}`}
                {!playlist.is_own && " · досыңыздың плейлисі"}
              </p>

              <div className="mt-5 flex items-center justify-center gap-3">
                {playlist.is_own ? (
                  <>
                    <IconButton label="Атын өзгерту" onClick={onRename}><Pencil size={18} /></IconButton>
                    <IconButton label="Бөлісу" onClick={onShare}><Share2 size={18} /></IconButton>
                  </>
                ) : (
                  <button onClick={onSave} disabled={saving} className="flex items-center gap-2 rounded-full bg-elevated px-4 py-2.5 text-[14px] font-semibold text-text active:scale-95 disabled:opacity-60">
                    {saving ? <Loader2 size={16} className="ui-spinner" /> : <Bookmark size={16} />} Өзіме сақтау
                  </button>
                )}
                <button
                  onClick={() => player.play(playlist.tracks, 0)}
                  disabled={!playlist.tracks.length}
                  aria-label="Ойнату"
                  className="qm-gradient flex h-16 w-16 items-center justify-center rounded-full text-white shadow-[0_10px_30px_rgba(124,58,237,0.4)] active:scale-95 disabled:opacity-50"
                >
                  <Play size={26} fill="currentColor" className="ml-1" />
                </button>
                <IconButton
                  label="Араластырып ойнату"
                  onClick={() => playlist.tracks.length && player.play(shuffled(playlist.tracks, Math.floor(Math.random() * playlist.tracks.length)), 0)}
                >
                  <Shuffle size={18} />
                </IconButton>
                {!playlist.is_own && <IconButton label="Бөлісу" onClick={onShare}><Share2 size={18} /></IconButton>}
              </div>

              <button
                onClick={onSend}
                disabled={sending || !playlist.tracks.length}
                className="mx-auto mt-4 flex items-center gap-2 rounded-full border border-music/40 bg-music/10 px-4 py-2 text-[13px] font-semibold text-music active:scale-95 disabled:opacity-50"
              >
                {sending ? <Loader2 size={15} className="ui-spinner" /> : <Send size={15} />}
                Бәрін Telegram-да тыңдау
              </button>

              <div className="mt-5 -mx-2">
                {playlist.tracks.length ? (
                  <TrackList tracks={playlist.tracks} numbered onMore={onMore} />
                ) : (
                  <p className="px-6 py-8 text-center text-[14px] text-muted">
                    Плейлист бос. Кез келген әннің «⋯» мәзірінен «Плейлистке қосу» таңдаңыз.
                  </p>
                )}
              </div>

              {playlist.is_own && (
                <button onClick={onDelete} className="mx-auto mt-8 flex items-center gap-2 text-[14px] font-semibold text-[#ff7770]">
                  <Trash2 size={16} /> Плейлистті жою
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function IconButton({ label, onClick, children }: { label: string; onClick: () => void; children: ReactNode }) {
  return (
    <button onClick={onClick} aria-label={label} className="flex h-11 w-11 items-center justify-center rounded-full bg-elevated text-text active:scale-95">
      {children}
    </button>
  );
}
