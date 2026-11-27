// Полноэкранный плеер: крупная обложка на размытом фоне, перемотка, очередь-режимы и
// главная для мобильных кнопка — «Telegram-да тыңдау»: трек уходит в чат, и плеер
// Telegram играет его с выключенным экраном (WebView на iOS этого не умеет).

import {
  ChevronDown,
  Heart,
  Loader2,
  MoreHorizontal,
  Pause,
  Play,
  Repeat,
  Repeat1,
  Send,
  Shuffle,
  SkipBack,
  SkipForward,
} from "../../ui-kit/adapters/icons";

import { haptic } from "../../lib/telegram";
import type { Track } from "../api";
import { duration } from "../format";
import { useLibrary } from "../useLibrary";
import { usePlayer } from "../usePlayer";
import Cover from "./Cover";

interface FullPlayerProps {
  onClose: () => void;
  onSend: (track: Track) => void;
  onMore: (track: Track) => void;
  sending: boolean;
}

export default function FullPlayer({ onClose, onSend, onMore, sending }: FullPlayerProps) {
  const player = usePlayer();
  const library = useLibrary();
  const track = player.current;
  if (!track) return null;
  const saved = library.has(track.id);
  const total = player.duration || track.duration_sec;
  const fill = total > 0 ? (player.position / total) * 100 : 0;

  return (
    <div className="anim-sheet fixed inset-0 z-50 flex flex-col overflow-hidden bg-bg" role="dialog" aria-modal="true" aria-label="Ойнатқыш">
      {/* Фон — та же обложка, размытая: экран окрашивается в цвет трека. */}
      <div className="pointer-events-none absolute inset-0 scale-125 opacity-60 blur-3xl" aria-hidden="true">
        <Cover title={track.title} performer={track.performer} url={track.cover_url} className="h-full w-full" rounded="" />
      </div>
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-black/30 via-bg/70 to-bg" aria-hidden="true" />

      <div className="relative mx-auto flex w-full max-w-md flex-1 flex-col px-6 pb-[calc(20px+var(--safe-bottom))] pt-[calc(12px+var(--safe-top))]">
        <div className="flex items-center justify-between">
          <button onClick={onClose} aria-label="Жабу" className="-ml-2 rounded-full p-2 text-text active:bg-white/10">
            <ChevronDown size={28} />
          </button>
          <span className="text-[11px] font-bold uppercase tracking-[0.2em] text-muted">QazaqMusic</span>
          <button onClick={() => onMore(track)} aria-label="Әрекеттер" className="-mr-2 rounded-full p-2 text-text active:bg-white/10">
            <MoreHorizontal size={24} />
          </button>
        </div>

        <div className="flex flex-1 items-center justify-center py-6">
          <div className={`aspect-square w-full max-w-[340px] overflow-hidden rounded-[28px] shadow-[0_24px_60px_rgba(0,0,0,0.55)] transition-transform duration-500 ${player.playing ? "scale-100" : "scale-[0.94]"}`}>
            <Cover title={track.title} performer={track.performer} url={track.cover_url} className="h-full w-full" rounded="" textSize="text-6xl" />
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-2xl font-extrabold tracking-tight text-text">{track.title}</h2>
            <p className="truncate text-[15px] text-muted">{track.performer}</p>
          </div>
          <button
            onClick={() => library.toggle(track.id)}
            aria-label={saved ? "Менің музыкамнан алып тастау" : "Менің музыкама қосу"}
            aria-pressed={saved}
            className={`rounded-full p-2 active:scale-90 ${saved ? "text-music-pink" : "text-muted"}`}
          >
            <Heart size={26} fill={saved ? "currentColor" : "none"} />
          </button>
        </div>

        {player.unavailable ? (
          <p className="mt-5 rounded-2xl border border-white/10 bg-white/5 p-3 text-[13px] leading-relaxed text-muted">
            Бұл ән тым үлкен немесе әзірге осында ашылмады. Оны Telegram-да тыңдаңыз — ол бот
            чатына келеді.
          </p>
        ) : (
          <div className="mt-5">
            <input
              type="range"
              min={0}
              max={Math.max(total, 1)}
              step={1}
              value={Math.min(player.position, total)}
              onChange={(event) => player.seek(Number(event.target.value))}
              aria-label="Перемотка"
              className="qm-range"
              style={{ ["--fill" as string]: `${fill}%` }}
            />
            <div className="mt-1.5 flex justify-between text-[12px] tabular text-faint">
              <span>{duration(player.position)}</span>
              <span>{duration(total)}</span>
            </div>
          </div>
        )}

        <div className="mt-4 flex items-center justify-between">
          <button
            onClick={() => { haptic.select(); player.toggleShuffle(); }}
            aria-label="Араластыру"
            aria-pressed={player.shuffle}
            className={`rounded-full p-2 ${player.shuffle ? "text-music" : "text-muted"}`}
          >
            <Shuffle size={22} />
          </button>
          <button onClick={() => { haptic.light(); player.prev(); }} aria-label="Алдыңғы" className="rounded-full p-2 text-text active:scale-95">
            <SkipBack size={30} fill="currentColor" />
          </button>
          <button
            onClick={() => { haptic.medium(); if (player.unavailable) onSend(track); else player.toggle(); }}
            aria-label={player.playing ? "Кідірту" : "Ойнату"}
            className="flex h-[72px] w-[72px] items-center justify-center rounded-full bg-white text-black shadow-[0_10px_30px_rgba(167,139,250,0.35)] active:scale-95"
          >
            {player.loading ? <Loader2 size={30} className="ui-spinner" /> : player.playing ? <Pause size={30} fill="currentColor" /> : <Play size={30} fill="currentColor" className="ml-1" />}
          </button>
          <button onClick={() => { haptic.light(); player.next(); }} aria-label="Келесі" className="rounded-full p-2 text-text active:scale-95">
            <SkipForward size={30} fill="currentColor" />
          </button>
          <button
            onClick={() => { haptic.select(); player.cycleRepeat(); }}
            aria-label="Қайталау"
            aria-pressed={player.repeat !== "off"}
            className={`rounded-full p-2 ${player.repeat !== "off" ? "text-music" : "text-muted"}`}
          >
            {player.repeat === "one" ? <Repeat1 size={22} /> : <Repeat size={22} />}
          </button>
        </div>

        <button
          onClick={() => onSend(track)}
          disabled={sending}
          className="qm-gradient mt-6 flex w-full items-center justify-center gap-2 rounded-2xl px-4 py-3.5 text-[15px] font-bold text-white shadow-[0_10px_30px_rgba(124,58,237,0.35)] active:scale-[0.98] disabled:opacity-60"
        >
          {sending ? <Loader2 size={18} className="ui-spinner" /> : <Send size={18} />}
          Telegram-да тыңдау
        </button>
        <p className="mt-2 text-center text-[12px] text-faint">Ән чатқа келеді — экран сөніп тұрса да ойнайды</p>
      </div>
    </div>
  );
}
