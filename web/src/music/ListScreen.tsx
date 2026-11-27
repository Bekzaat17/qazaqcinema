// Экран списка: свой плейлист, чужой (по ссылке или из «Тыңдаушылардың плейлистері»)
// и готовая подборка. Всё слушается одинаково — «Ойнату» отправляет список в чат по
// порядку, тап по треку — он и всё, что после него.
//
// Свой плейлист ещё и правится: переименовать, «Бәріне көрсету», «Реттеу», удалить.
// Чужой и подборку можно сохранить себе копией.

import { useEffect, useState, type ReactNode } from "react";

import {
  ArrowLeft,
  ArrowUpDown,
  Bookmark,
  Check,
  Globe,
  ListMusic,
  Loader2,
  Pencil,
  Play,
  Share2,
  Trash2,
  type LucideIcon,
} from "../ui-kit/adapters/icons";

import { SEND_MAX, type Track } from "./api";
import PlaylistCover from "./components/PlaylistCover";
import TrackList from "./components/TrackList";
import { duration, tracksLabel } from "./format";

export interface ListData {
  kind: "own" | "shared" | "collection";
  title: string;
  subtitle: string;
  tracks: Track[];
  isPublic?: boolean;
  Icon?: LucideIcon;
}

interface ListScreenProps {
  data: ListData | null;
  failed: boolean;
  busy: boolean;
  saving: boolean;
  onBack: () => void;
  onSend: (tracks: Track[]) => void;
  onMore: (track: Track) => void;
  onShare?: () => void;
  onRename?: () => void;
  onDelete?: () => void;
  onSave?: () => void;
  onTogglePublic?: (value: boolean) => void;
  onReorder?: (tracks: Track[]) => Promise<boolean>;
}

export default function ListScreen(props: ListScreenProps) {
  const { data, failed, busy, saving, onBack, onSend, onMore, onShare, onRename, onDelete, onSave, onTogglePublic, onReorder } = props;
  const [draft, setDraft] = useState<Track[] | null>(null);
  const [storing, setStoring] = useState(false);
  useEffect(() => setDraft(null), [data?.title, data?.kind]);

  const tracks = draft ?? data?.tracks ?? [];
  const total = tracks.reduce((sum, track) => sum + track.duration_sec, 0);
  const own = data?.kind === "own";

  const finishReorder = async () => {
    if (!draft || !onReorder) return;
    setStoring(true);
    const ok = await onReorder(draft);
    setStoring(false);
    if (ok) setDraft(null);
  };

  return (
    <div className="anim-fade fixed inset-0 z-[35] overflow-y-auto bg-bg pb-[calc(110px+var(--safe-bottom))]">
      <div className="relative">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-96 overflow-hidden" aria-hidden="true">
          <div className="h-full w-full scale-150 opacity-45 blur-3xl">
            {data && <PlaylistCover seed={data.title} />}
          </div>
          <div className="absolute inset-0 bg-gradient-to-b from-transparent via-bg/60 to-bg" />
        </div>
        <div className="relative mx-auto max-w-[1024px] px-4 pt-[calc(12px+var(--safe-top))]">
          <button onClick={onBack} aria-label="Артқа" className="-ml-2 rounded-full p-2 text-text active:bg-white/10">
            <ArrowLeft size={24} />
          </button>
          {!data ? (
            <div className="flex justify-center py-24 text-muted">
              {failed ? <p className="text-[15px]">Табылмады.</p> : <Loader2 className="ui-spinner" />}
            </div>
          ) : (
            <>
              <div className="mx-auto mt-2 aspect-square w-48 overflow-hidden rounded-[28px] shadow-[0_20px_50px_rgba(0,0,0,0.5)]">
                <PlaylistCover seed={data.title} Icon={data.Icon ?? ListMusic} />
              </div>
              <h1 className="mt-5 text-center text-[24px] font-extrabold tracking-tight text-text">{data.title}</h1>
              <p className="mt-1 text-center text-[13px] text-muted">
                {data.subtitle ? `${data.subtitle} · ` : ""}
                {tracksLabel(tracks.length)}
                {total > 0 && ` · ${duration(total)}`}
              </p>

              {draft ? (
                <div className="mt-5 flex items-center justify-center gap-3">
                  <button onClick={() => setDraft(null)} className="rounded-full bg-elevated px-4 py-2.5 text-[14px] font-semibold text-muted">Болдырмау</button>
                  <button onClick={() => void finishReorder()} disabled={storing} className="qm-gradient flex items-center gap-2 rounded-full px-5 py-2.5 text-[14px] font-bold text-white disabled:opacity-60">
                    {storing ? <Loader2 size={16} className="ui-spinner" /> : <Check size={16} />} Дайын
                  </button>
                </div>
              ) : (
                <>
                  <div className="mt-5 flex items-center justify-center gap-3">
                    {own && onRename && <Round label="Атын өзгерту" onClick={onRename}><Pencil size={18} /></Round>}
                    {!own && onSave && (
                      <Round label="Өзіме сақтау" onClick={onSave} disabled={saving}>
                        {saving ? <Loader2 size={18} className="ui-spinner" /> : <Bookmark size={18} />}
                      </Round>
                    )}
                    <button
                      onClick={() => onSend(tracks.slice(0, SEND_MAX))}
                      disabled={!tracks.length || busy}
                      aria-label="Ойнату — бәрін чатқа ретімен жіберу"
                      className="qm-gradient flex h-16 w-16 items-center justify-center rounded-full text-white shadow-[0_10px_30px_rgba(124,58,237,0.4)] active:scale-95 disabled:opacity-50"
                    >
                      {busy ? <Loader2 size={26} className="ui-spinner" /> : <Play size={26} fill="currentColor" className="ml-1" />}
                    </button>
                    {own && onReorder && (
                      <Round label="Реттеу" onClick={() => setDraft([...tracks])} disabled={tracks.length < 2}>
                        <ArrowUpDown size={18} />
                      </Round>
                    )}
                    {onShare && <Round label="Бөлісу" onClick={onShare}><Share2 size={18} /></Round>}
                  </div>
                  <p className="mx-auto mt-3 max-w-xs text-center text-[12px] leading-relaxed text-faint">
                    «Ойнату» бәрін чатқа ретімен жібереді — Telegram оларды бірінен соң бірін ойнатады, экран сөнсе де.
                    {tracks.length > SEND_MAX && ` Бір басқанда ${SEND_MAX} ән.`}
                  </p>
                  {own && onTogglePublic && (
                    <label className="mx-auto mt-4 flex max-w-sm cursor-pointer items-center gap-3 rounded-2xl border border-white/5 bg-surface px-4 py-3">
                      <Globe size={18} className="shrink-0 text-music" />
                      <span className="min-w-0 flex-1">
                        <span className="block text-[14px] font-semibold text-text">Бәріне көрсету</span>
                        <span className="block text-[12px] text-faint">Плейлист «Тыңдаушылардың плейлистері» бөлімінде шығады</span>
                      </span>
                      <input
                        type="checkbox"
                        role="switch"
                        checked={Boolean(data.isPublic)}
                        onChange={(event) => onTogglePublic(event.target.checked)}
                        className="h-6 w-11 shrink-0 cursor-pointer appearance-none rounded-full bg-white/15 transition-colors before:block before:h-5 before:w-5 before:translate-x-0.5 before:translate-y-0.5 before:rounded-full before:bg-white before:transition-transform checked:bg-music checked:before:translate-x-[22px]"
                      />
                    </label>
                  )}
                </>
              )}

              <div className="-mx-2 mt-5">
                {tracks.length ? (
                  <TrackList
                    tracks={tracks}
                    numbered
                    queue
                    busy={busy}
                    onSend={onSend}
                    onMore={onMore}
                    onReorder={draft ? setDraft : undefined}
                  />
                ) : (
                  <p className="px-6 py-8 text-center text-[14px] text-muted">
                    Плейлист бос. Кез келген әннің «⋯» мәзірінен «Плейлистке қосу» таңдаңыз.
                  </p>
                )}
              </div>

              {own && onDelete && !draft && (
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

function Round({ label, onClick, disabled, children }: { label: string; onClick: () => void; disabled?: boolean; children: ReactNode }) {
  return (
    <button onClick={onClick} disabled={disabled} aria-label={label} title={label} className="flex h-11 w-11 items-center justify-center rounded-full bg-elevated text-text active:scale-95 disabled:opacity-40">
      {children}
    </button>
  );
}
