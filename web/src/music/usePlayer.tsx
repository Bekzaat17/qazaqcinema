// Плеер Mini App — один <audio> на весь раздел и очередь треков.
//
// Контекст, а не локальное состояние экрана: играет одно и то же, пока человек ходит
// между главной, своей музыкой и плейлистами, а мини-плеер внизу видит каждый экран.
//
// ⚠️ WebView Telegram на iOS останавливает звук, когда Mini App свёрнут. Поэтому для
// прослушивания «с выключенным экраном» есть отдельная дорога — трек уходит в чат
// (плеер Telegram играет в фоне), и полноэкранный плеер называет её прямо.
//
// Media Session даёт кнопки на экране блокировки и в шторке уведомлений Android: там,
// где WebView звук не глушит, человек управляет музыкой не открывая Telegram.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { musicApi, type Track } from "./api";
import { nextIndex, nextPlayable, shuffled } from "./format";

export type Repeat = "off" | "all" | "one";

// Прослушивание засчитывается после стольких секунд: случайный тап — не прослушивание.
const PLAYED_AFTER_SEC = 10;

interface PlayerValue {
  current: Track | null;
  queue: Track[];
  index: number;
  playing: boolean;
  loading: boolean;
  /** Трек нельзя слушать здесь (тяжёлый файл или сбой) — только в чате с ботом. */
  unavailable: boolean;
  position: number;
  duration: number;
  repeat: Repeat;
  shuffle: boolean;
  play: (tracks: Track[], startIndex?: number) => void;
  toggle: () => void;
  next: () => void;
  prev: () => void;
  seek: (seconds: number) => void;
  cycleRepeat: () => void;
  toggleShuffle: () => void;
}

const PlayerContext = createContext<PlayerValue | null>(null);

export function PlayerProvider({ children }: { children: ReactNode }) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [queue, setQueue] = useState<Track[]>([]);
  const [baseQueue, setBaseQueue] = useState<Track[]>([]);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [position, setPosition] = useState(0);
  const [duration, setDuration] = useState(0);
  const [repeat, setRepeat] = useState<Repeat>("off");
  const [shuffle, setShuffle] = useState(false);
  const reported = useRef(new Set<number>());
  // Свежие значения для обработчиков <audio>, повешенных один раз.
  const state = useRef({ queue, index, repeat });
  state.current = { queue, index, repeat };

  const current = queue[index] ?? null;

  if (audioRef.current === null && typeof Audio !== "undefined") {
    audioRef.current = new Audio();
    audioRef.current.preload = "auto";
  }

  const goTo = useCallback((target: number | null) => {
    const audio = audioRef.current;
    if (target === null) {
      audio?.pause();
      if (audio) audio.currentTime = 0;
      setPlaying(false);
      return;
    }
    setIndex(target);
  }, []);

  // Смена трека → новый источник. Без stream_url трек живёт только в Telegram.
  // Зависимость — id и ссылка, а не объект: тот же трек, пришедший из другого списка
  // новым объектом, не должен перезапускаться с начала.
  const currentId = current?.id;
  const currentStream = current?.stream_url;
  useEffect(() => {
    const audio = audioRef.current;
    const track = state.current.queue[state.current.index];
    if (!audio || !track) return;
    setPosition(0);
    setDuration(track.duration_sec);
    if (!track.stream_url) {
      audio.pause();
      audio.removeAttribute("src");
      setUnavailable(true);
      setPlaying(false);
      return;
    }
    setUnavailable(false);
    setLoading(true);
    audio.src = track.stream_url;
    audio.play().then(
      () => setPlaying(true),
      () => {
        // Автозапуск запрещён — ждём тапа по «Ойнату».
        setPlaying(false);
        setLoading(false);
      },
    );
  }, [currentId, currentStream]);

  // Обработчики <audio> вешаются один раз.
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onTime = () => {
      setPosition(audio.currentTime);
      const track = state.current.queue[state.current.index];
      if (track && audio.currentTime >= PLAYED_AFTER_SEC && !reported.current.has(track.id)) {
        reported.current.add(track.id);
        void musicApi.played(track.id).catch(() => {});
      }
    };
    const onMeta = () => {
      if (Number.isFinite(audio.duration) && audio.duration > 0) setDuration(audio.duration);
    };
    const onEnded = () => {
      const { queue: list, index: at, repeat: mode } = state.current;
      if (mode === "one") {
        audio.currentTime = 0;
        void audio.play();
        return;
      }
      goTo(nextPlayable(list, at, mode));
    };
    const onError = () => {
      setLoading(false);
      setPlaying(false);
      setUnavailable(true);
    };
    const onPlaying = () => {
      setLoading(false);
      setPlaying(true);
    };
    const onPause = () => setPlaying(false);
    const onWaiting = () => setLoading(true);
    audio.addEventListener("timeupdate", onTime);
    audio.addEventListener("loadedmetadata", onMeta);
    audio.addEventListener("ended", onEnded);
    audio.addEventListener("error", onError);
    audio.addEventListener("playing", onPlaying);
    audio.addEventListener("pause", onPause);
    audio.addEventListener("waiting", onWaiting);
    return () => {
      audio.removeEventListener("timeupdate", onTime);
      audio.removeEventListener("loadedmetadata", onMeta);
      audio.removeEventListener("ended", onEnded);
      audio.removeEventListener("error", onError);
      audio.removeEventListener("playing", onPlaying);
      audio.removeEventListener("pause", onPause);
      audio.removeEventListener("waiting", onWaiting);
    };
  }, [goTo]);

  // Плеер живёт, пока открыт музыкальный раздел: ушли в кинотеатр — звук гасим.
  useEffect(() => () => audioRef.current?.pause(), []);

  const play = useCallback(
    (tracks: Track[], startIndex = 0) => {
      if (tracks.length === 0) return;
      const start = Math.min(Math.max(startIndex, 0), tracks.length - 1);
      const sameTrack = queue[index]?.id === tracks[start].id;
      setBaseQueue(tracks);
      if (shuffle) {
        setQueue(shuffled(tracks, start));
        setIndex(0);
      } else {
        setQueue(tracks);
        setIndex(start);
      }
      if (sameTrack) {
        // Тот же трек из другого списка: не перезапускаем, просто продолжаем.
        void audioRef.current?.play().catch(() => {});
      }
    },
    [queue, index, shuffle],
  );

  const toggle = useCallback(() => {
    const audio = audioRef.current;
    if (!audio || !current || unavailable) return;
    if (audio.paused) void audio.play().catch(() => setPlaying(false));
    else audio.pause();
  }, [current, unavailable]);

  const next = useCallback(() => {
    goTo(nextIndex(index, queue.length, repeat === "one" ? "all" : repeat) ?? (queue.length ? 0 : null));
  }, [goTo, index, queue.length, repeat]);

  const prev = useCallback(() => {
    const audio = audioRef.current;
    // Как в любом плеере: в начале трека — предыдущий, дальше — к началу текущего.
    if (audio && audio.currentTime > 3) {
      audio.currentTime = 0;
      return;
    }
    goTo(index > 0 ? index - 1 : queue.length ? queue.length - 1 : null);
  }, [goTo, index, queue.length]);

  const seek = useCallback((seconds: number) => {
    const audio = audioRef.current;
    if (!audio || !Number.isFinite(seconds)) return;
    audio.currentTime = Math.max(0, seconds);
    setPosition(audio.currentTime);
  }, []);

  const cycleRepeat = useCallback(() => {
    setRepeat((mode) => (mode === "off" ? "all" : mode === "all" ? "one" : "off"));
  }, []);

  const toggleShuffle = useCallback(() => {
    setShuffle((on) => {
      const playingTrack = queue[index];
      if (!playingTrack) return !on;
      if (on) {
        const restored = baseQueue.length ? baseQueue : queue;
        setQueue(restored);
        setIndex(Math.max(0, restored.findIndex((t) => t.id === playingTrack.id)));
      } else {
        setQueue(shuffled(queue, index));
        setIndex(0);
      }
      return !on;
    });
  }, [baseQueue, queue, index]);

  // Media Session: экран блокировки, шторка Android, кнопки наушников.
  useEffect(() => {
    const session = typeof navigator !== "undefined" ? navigator.mediaSession : undefined;
    if (!session || !current) return;
    try {
      session.metadata = new MediaMetadata({
        title: current.title,
        artist: current.performer,
        album: "QazaqMusic",
        artwork: current.cover_url
          ? [{ src: current.cover_url, sizes: "320x320", type: "image/jpeg" }]
          : [{ src: "/logo-icon.png", sizes: "512x512", type: "image/png" }],
      });
      session.setActionHandler("play", () => void audioRef.current?.play());
      session.setActionHandler("pause", () => audioRef.current?.pause());
      session.setActionHandler("nexttrack", next);
      session.setActionHandler("previoustrack", prev);
      session.setActionHandler("seekto", (details) => {
        if (details.seekTime !== undefined) seek(details.seekTime);
      });
    } catch {
      /* старый WebView без части действий — кнопки просто не появятся */
    }
  }, [current, next, prev, seek]);

  const value = useMemo<PlayerValue>(
    () => ({
      current,
      queue,
      index,
      playing,
      loading,
      unavailable,
      position,
      duration,
      repeat,
      shuffle,
      play,
      toggle,
      next,
      prev,
      seek,
      cycleRepeat,
      toggleShuffle,
    }),
    [current, queue, index, playing, loading, unavailable, position, duration, repeat, shuffle,
      play, toggle, next, prev, seek, cycleRepeat, toggleShuffle],
  );

  return <PlayerContext.Provider value={value}>{children}</PlayerContext.Provider>;
}

export function usePlayer(): PlayerValue {
  const value = useContext(PlayerContext);
  if (!value) throw new Error("usePlayer вне PlayerProvider");
  return value;
}
