// Страница трека в Mini App: цифры («сколько людей слушают»), исполнитель, похожие и
// плейлисты с этим треком. Отсюда же — тыңдау, к себе, в плейлист, поделиться.

import type { ReactNode } from "react";

import { ArrowLeft, Heart, ListMusic, ListPlus, Loader2, Play, Share2, Sparkles, User } from "../ui-kit/adapters/icons";

import type { Playlist, Track, TrackDetail } from "./api";
import Cover from "./components/Cover";
import PlaylistCover from "./components/PlaylistCover";
import TrackList from "./components/TrackList";
import { duration, tracksLabel } from "./format";
import { useLibrary } from "./useLibrary";

interface TrackScreenProps {
  detail: TrackDetail | null;
  failed: boolean;
  busy: boolean;
  onBack: () => void;
  onSend: (tracks: Track[]) => void;
  onMore: (track: Track) => void;
  onAddToPlaylist: (track: Track) => void;
  onShare: (track: Track) => void;
  onOpenArtist: (slug: string) => void;
  onOpenPlaylist: (playlist: Playlist) => void;
}

export default function TrackScreen(props: TrackScreenProps) {
  const { detail, failed, busy, onBack, onSend, onMore, onAddToPlaylist, onShare, onOpenArtist, onOpenPlaylist } = props;
  const library = useLibrary();
  const track = detail?.track;
  const saved = track ? library.has(track.id) : false;

  return (
    <div className="anim-fade fixed inset-0 z-[37] overflow-y-auto bg-bg pb-[calc(110px+var(--safe-bottom))]">
      <div className="mx-auto max-w-[1024px] px-4 pt-[calc(12px+var(--safe-top))]">
        <button onClick={onBack} aria-label="Артқа" className="-ml-2 rounded-full p-2 text-text active:bg-white/10">
          <ArrowLeft size={24} />
        </button>
        {!detail || !track ? (
          <div className="flex justify-center py-24 text-muted">
            {failed ? <p className="text-[15px]">Ән табылмады.</p> : <Loader2 className="ui-spinner" />}
          </div>
        ) : (
          <>
            <div className="mx-auto mt-2 aspect-square w-48 overflow-hidden rounded-[28px] shadow-[0_20px_50px_rgba(0,0,0,0.5)]">
              <Cover title={track.title} performer={track.performer} className="h-full w-full" rounded="" textSize="text-5xl" />
            </div>
            <h1 className="mt-5 text-center text-[24px] font-extrabold tracking-tight text-text">{track.title}</h1>
            <button onClick={() => onOpenArtist(detail.artist_slug)} className="mx-auto mt-1 block text-[15px] font-semibold text-music">
              {track.performer}
            </button>
            <p className="mt-1 text-center text-[13px] text-faint">{duration(track.duration_sec)}</p>

            <div className="mt-4 flex flex-wrap justify-center gap-2">
              <Stat>🎧 {detail.listeners} адам тыңдады</Stat>
              <Stat>📂 {detail.playlists_count} плейлистте</Stat>
              <Stat>❤️ {detail.saves} сақтады</Stat>
            </div>

            <div className="mt-5 flex items-center justify-center gap-3">
              <Round label={saved ? "Менің музыкамнан алып тастау" : "Менің музыкама қосу"} onClick={() => library.toggle(track.id)}>
                <Heart size={19} className={saved ? "text-music-pink" : ""} fill={saved ? "currentColor" : "none"} />
              </Round>
              <button
                onClick={() => onSend([track])}
                disabled={busy}
                aria-label="Telegram-да тыңдау"
                className="qm-gradient flex h-16 w-16 items-center justify-center rounded-full text-white shadow-[0_10px_30px_rgba(124,58,237,0.4)] active:scale-95 disabled:opacity-50"
              >
                {busy ? <Loader2 size={26} className="ui-spinner" /> : <Play size={26} fill="currentColor" className="ml-1" />}
              </button>
              <Round label="Плейлистке қосу" onClick={() => onAddToPlaylist(track)}><ListPlus size={19} /></Round>
              <Round label="Бөлісу" onClick={() => onShare(track)}><Share2 size={19} /></Round>
            </div>
            <p className="mt-3 text-center text-[12px] text-faint">Ән чатқа келеді — экран сөнсе де ойнайды.</p>

            {detail.by_artist.length > 0 && (
              <Section Icon={User} title={`${track.performer} — басқа әндері`}>
                <TrackList tracks={detail.by_artist} busy={busy} onSend={onSend} onMore={onMore} />
              </Section>
            )}
            {detail.similar.length > 0 && (
              <Section Icon={Sparkles} title="Ұқсас әндер">
                <TrackList tracks={detail.similar} busy={busy} onSend={onSend} onMore={onMore} />
              </Section>
            )}
            {detail.playlists.length > 0 && (
              <Section Icon={ListMusic} title="Осы ән бар плейлистер">
                <div className="no-scrollbar -mx-2 flex snap-x scroll-px-4 gap-3 overflow-x-auto px-2 pb-1">
                  {detail.playlists.map((playlist) => (
                    <button key={playlist.id} onClick={() => onOpenPlaylist(playlist)} className="w-32 shrink-0 snap-start text-left active:scale-[0.98]">
                      <div className="aspect-square overflow-hidden rounded-3xl"><PlaylistCover seed={playlist.title} /></div>
                      <p className="mt-2 truncate text-[14px] font-semibold text-text">{playlist.title}</p>
                      <p className="text-[12px] text-faint">{tracksLabel(playlist.track_count)}</p>
                    </button>
                  ))}
                </div>
              </Section>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function Stat({ children }: { children: ReactNode }) {
  return <span className="rounded-full border border-white/10 bg-surface px-3 py-1 text-[12px] font-semibold text-muted">{children}</span>;
}

function Round({ label, onClick, children }: { label: string; onClick: () => void; children: ReactNode }) {
  return (
    <button onClick={onClick} aria-label={label} title={label} className="flex h-11 w-11 items-center justify-center rounded-full bg-elevated text-text active:scale-95">
      {children}
    </button>
  );
}

function Section({ Icon, title, children }: { Icon: typeof User; title: string; children: ReactNode }) {
  return (
    <section className="mt-7">
      <h2 className="mb-2 flex items-center gap-2 text-[17px] font-extrabold tracking-tight text-text">
        <Icon size={18} className="text-music" /> {title}
      </h2>
      <div className="-mx-2">{children}</div>
    </section>
  );
}
