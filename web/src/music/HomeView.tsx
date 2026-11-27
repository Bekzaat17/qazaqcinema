// Басты: поиск по всему каталогу, новые и популярные, и что ищут, но нет.

import { useEffect, useState, type ReactNode } from "react";

import { Flame, Loader2, Music2, Plus, Search, SearchX, Send, Sparkles, Trophy, TrendingUp, Users, X, type LucideIcon } from "../ui-kit/adapters/icons";

import { openBotChat } from "../lib/telegram";

import { musicApi, type Collection, type MusicHome, type Playlist, type Track } from "./api";
import PlaylistCover from "./components/PlaylistCover";
import TrackList from "./components/TrackList";
import { tracksLabel } from "./format";

/** Значок готовой подборки по её ключу (подпись приходит с бэка). */
export const COLLECTION_ICONS: Record<string, LucideIcon> = {
  week_hits: Flame,
  new: Sparkles,
  best: Trophy,
};

interface HomeViewProps {
  home: MusicHome | null;
  collections: Collection[];
  publicPlaylists: Playlist[];
  failed: boolean;
  busy: boolean;
  onRetry: () => void;
  onSend: (tracks: Track[]) => void;
  onMore: (track: Track) => void;
  onOpenCollection: (collection: Collection) => void;
  onOpenPlaylist: (playlist: Playlist) => void;
  onRequest: (query: string) => void;
  onAdd: () => void;
}

const DEBOUNCE_MS = 350;
const SHELF_SHOWN = 8;

function useTrackSearch(query: string) {
  const [results, setResults] = useState<Track[] | null>(null);
  useEffect(() => {
    const text = query.trim();
    if (!text) {
      setResults(null);
      return;
    }
    let alive = true;
    setResults(null);
    const timer = setTimeout(() => {
      musicApi.tracks({ q: text, limit: 50 }).then(
        (found) => alive && setResults(found),
        () => alive && setResults([]),
      );
    }, DEBOUNCE_MS);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [query]);
  return results;
}

function Section({ Icon, title, children }: { Icon: LucideIcon; title: string; children: ReactNode }) {
  return (
    <section className="mt-6">
      <h2 className="mb-2 flex items-center gap-2 px-4 text-[17px] font-extrabold tracking-tight text-text">
        <Icon size={18} className="text-music" />
        {title}
      </h2>
      <div className="px-2">{children}</div>
    </section>
  );
}

function Rail({ children }: { children: ReactNode }) {
  return <div className="no-scrollbar -mx-2 flex snap-x scroll-px-4 gap-3 overflow-x-auto px-4 pb-1">{children}</div>;
}

function Tile({ seed, Icon, title, caption, onClick }: { seed: string; Icon?: LucideIcon; title: string; caption: string; onClick: () => void }) {
  return (
    <button onClick={onClick} className="w-36 shrink-0 snap-start text-left active:scale-[0.98]">
      <div className="aspect-square overflow-hidden rounded-3xl shadow-[0_8px_24px_rgba(0,0,0,0.35)]">
        <PlaylistCover seed={seed} Icon={Icon} />
      </div>
      <p className="mt-2 truncate text-[14px] font-semibold text-text">{title}</p>
      <p className="line-clamp-2 text-[12px] leading-snug text-faint">{caption}</p>
    </button>
  );
}

export default function HomeView(props: HomeViewProps) {
  const { home, collections, publicPlaylists, failed, busy, onRetry, onSend, onMore, onOpenCollection, onOpenPlaylist, onRequest, onAdd } = props;
  const [query, setQuery] = useState("");
  const [showAllNew, setShowAllNew] = useState(false);
  const results = useTrackSearch(query);
  const searching = query.trim().length > 0;

  return (
    <div className="pb-6">
      <div className="sticky top-[57px] z-20 bg-bg/90 px-4 pb-2 pt-3 backdrop-blur-xl">
        <label className="flex items-center gap-2 rounded-2xl border border-white/5 bg-surface px-3.5 py-3 focus-within:border-music/60">
          <Search size={18} className="text-faint" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Ән немесе орындаушы"
            enterKeyHint="search"
            className="min-w-0 flex-1 bg-transparent text-[15px] text-text placeholder:text-faint focus:outline-none"
          />
          {query && (
            <button onClick={() => setQuery("")} aria-label="Тазалау" className="text-faint">
              <X size={18} />
            </button>
          )}
        </label>
      </div>

      {searching ? (
        <div className="px-2 pt-2">
          {results === null ? (
            <div className="flex justify-center py-10 text-muted"><Loader2 className="ui-spinner" /></div>
          ) : results.length ? (
            <TrackList tracks={results} busy={busy} onSend={onSend} onMore={onMore} />
          ) : (
            <div className="px-4 py-10 text-center">
              <SearchX size={36} className="mx-auto text-faint" />
              <p className="mt-3 text-[15px] font-semibold text-text">«{query.trim()}» әзірге жоқ</p>
              {/* Короткая дорога «не нашёл → нашёл → добавил»: Mini App не видит чатов
                  человека, поэтому песню он находит в Telegram сам и пересылает боту. */}
              <ol className="mt-4 space-y-2 rounded-2xl border border-white/5 bg-surface p-3 text-left text-[13px] leading-relaxed text-muted">
                <li><span className="mr-1.5 font-bold text-music">1.</span>Telegram-да іздеңіз: іздеу жолына ән атын жазып, <b className="text-text">«Музыка»</b> бөлімін ашыңыз.</li>
                <li><span className="mr-1.5 font-bold text-music">2.</span>Тапқан әнді ботқа <b className="text-text">қайта жіберіңіз</b> (forward).</li>
                <li><span className="mr-1.5 font-bold text-music">3.</span>Осында оралыңыз — ән іздеуде және «Менің музыкам» бөлімінде тұрады.</li>
              </ol>
              <div className="mt-4 flex flex-col gap-2">
                <button onClick={() => openBotChat()} className="qm-gradient flex items-center justify-center gap-2 rounded-2xl px-4 py-3 text-[15px] font-bold text-white active:scale-[0.98]">
                  <Send size={17} /> Ботты ашу
                </button>
                <button onClick={() => onRequest(query.trim())} className="rounded-2xl bg-elevated px-4 py-3 text-[15px] font-semibold text-text active:scale-[0.98]">
                  Таппадым — сұраныс қалдыру
                </button>
              </div>
              <p className="mt-2 text-[12px] text-faint">Сұраныс қалдырсаңыз, ән қосылғанда бот сізге хабарлайды.</p>
            </div>
          )}
        </div>
      ) : (
        <>
          <div className="mx-4 mt-2 overflow-hidden rounded-3xl qm-gradient p-5 text-white shadow-[0_16px_40px_rgba(124,58,237,0.3)]">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-white/70">QazaqMusic</p>
                <h1 className="mt-1 text-[22px] font-extrabold leading-tight tracking-tight">Бәріміз бірге толтыратын музыка</h1>
                <p className="mt-1.5 text-[13px] leading-relaxed text-white/80">
                  Әнді бас — ол чатқа келеді, экран сөнсе де ойнайды. Плейлист жина, досыңа бөліс, жоқ әнді ботқа жібер.
                </p>
              </div>
              <Music2 size={40} className="shrink-0 text-white/80" />
            </div>
            <button onClick={onAdd} className="mt-4 flex items-center gap-2 rounded-full bg-white px-4 py-2 text-[14px] font-bold text-music-600 active:scale-95">
              <Plus size={16} /> Ән қосу
            </button>
          </div>

          {failed && !home && (
            <div className="px-4 py-10 text-center">
              <p className="text-[15px] text-muted">Музыка жүктелмеді.</p>
              <button onClick={onRetry} className="mt-3 rounded-full bg-elevated px-5 py-2.5 text-[14px] font-semibold text-text">Қайталау</button>
            </div>
          )}
          {!home && !failed && <div className="flex justify-center py-12 text-muted"><Loader2 className="ui-spinner" /></div>}

          {home && home.recent.length === 0 && (
            <div className="px-6 py-10 text-center">
              <p className="text-[15px] font-semibold text-text">Каталог енді ашылды</p>
              <p className="mt-1 text-[13px] text-muted">Бірінші болып ән қосыңыз — ол бірден бәріне көрінеді.</p>
            </div>
          )}

          {collections.length > 0 && (
            <Section Icon={Music2} title="Дайын плейлистер">
              <Rail>
                {collections.map((collection) => (
                  <Tile
                    key={collection.key}
                    seed={collection.title}
                    Icon={COLLECTION_ICONS[collection.key]}
                    title={collection.title}
                    caption={collection.performers.length ? `${collection.performers.join(", ")} және т.б.` : collection.subtitle}
                    onClick={() => onOpenCollection(collection)}
                  />
                ))}
              </Rail>
            </Section>
          )}

          {publicPlaylists.length > 0 && (
            <Section Icon={Users} title="Тыңдаушылардың плейлистері">
              <Rail>
                {publicPlaylists.map((playlist) => (
                  <Tile
                    key={playlist.id}
                    seed={playlist.title}
                    title={playlist.title}
                    caption={`${tracksLabel(playlist.track_count)}${playlist.saves_count ? ` · ${playlist.saves_count} адам сақтады` : ""}`}
                    onClick={() => onOpenPlaylist(playlist)}
                  />
                ))}
              </Rail>
            </Section>
          )}

          {home && home.popular.length > 0 && (
            <Section Icon={TrendingUp} title="Танымал">
              <TrackList tracks={home.popular.slice(0, 10)} numbered busy={busy} onSend={onSend} onMore={onMore} />
            </Section>
          )}

          {home && home.recent.length > 0 && (
            <Section Icon={Sparkles} title="Жаңа қосылған">
              <TrackList tracks={showAllNew ? home.recent : home.recent.slice(0, SHELF_SHOWN)} busy={busy} onSend={onSend} onMore={onMore} />
              {!showAllNew && home.recent.length > SHELF_SHOWN && (
                <button onClick={() => setShowAllNew(true)} className="mx-2 mt-1 w-[calc(100%-16px)] rounded-2xl bg-surface py-2.5 text-[14px] font-semibold text-muted active:bg-elevated">
                  Тағы көрсету
                </button>
              )}
            </Section>
          )}

          {home && home.requests.length > 0 && (
            <Section Icon={Search} title="Іздеп жүр, бірақ әлі жоқ">
              <p className="px-2 pb-2 text-[13px] text-muted">Сізде бар ма? Ботқа жіберіңіз — бәрі рақмет айтады 🙌</p>
              <div className="flex flex-wrap gap-2 px-2">
                {home.requests.map((request) => (
                  <button key={request.query} onClick={onAdd} className="rounded-full border border-white/10 bg-surface px-3 py-1.5 text-[13px] text-text active:bg-elevated">
                    {request.query}
                    {request.votes > 1 && <span className="ml-1.5 text-music">×{request.votes}</span>}
                  </button>
                ))}
              </div>
            </Section>
          )}
        </>
      )}
    </div>
  );
}
