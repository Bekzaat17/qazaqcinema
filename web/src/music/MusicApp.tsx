// QazaqMusic — музыкальный раздел Mini App.
//
// Отдельная оболочка со своей навигацией (Басты · Менің музыкам · Қосу), но та же
// сессия, тот же бот и те же примитивы (Sheet, Toast, BotStartSheet). Раздел бесплатный:
// здесь нет ни пэйволла, ни подарков — только авторизация, чтобы знать, чья коллекция.
//
// Оверлеи живут стеком, и нативная кнопка «назад» Telegram закрывает верхний из них:
// шторку → полный плеер → экран плейлиста.

import { useCallback, useEffect, useState } from "react";

import { Clapperboard, Home, Library, PlusCircle, type LucideIcon } from "../ui-kit/adapters/icons";

import BotStartSheet from "../components/BotStartSheet";
import { LoadError, NotInTelegram, SessionExpired } from "../components/States";
import Toast from "../components/Toast";
import { useTelegramBackButton } from "../hooks/useTelegramBackButton";
import { ApiError, api, SessionExpiredError } from "../lib/api";
import { BOT_USERNAME, getInitData, haptic, openTelegramLink } from "../lib/telegram";
import { Brand } from "../ui-kit";
import AddView from "./AddView";
import { musicApi, type MusicHome, type Playlist, type PlaylistDetail, type Track } from "./api";
import FullPlayer from "./components/FullPlayer";
import MiniPlayer from "./components/MiniPlayer";
import PlaylistPicker from "./components/PlaylistPicker";
import TextPrompt from "./components/TextPrompt";
import TrackSheet from "./components/TrackSheet";
import HomeView from "./HomeView";
import { musicTarget, navigateApp, shareLink, trackShareUrl } from "./launch";
import LibraryView from "./LibraryView";
import PlaylistScreen from "./PlaylistScreen";
import { LibraryProvider } from "./useLibrary";
import { PlayerProvider, usePlayer } from "./usePlayer";

type Tab = "home" | "library" | "add";
type Phase = "loading" | "ready" | "error" | "no_telegram" | "session_expired";

type Prompt =
  | { kind: "create"; track: Track | null }
  | { kind: "rename"; playlist: PlaylistDetail }
  | { kind: "request"; initial: string };

type OpenPlaylist = { id: number } | { code: string };

const TABS: { id: Tab; label: string; Icon: LucideIcon }[] = [
  { id: "home", label: "Басты", Icon: Home },
  { id: "library", label: "Менің музыкам", Icon: Library },
  { id: "add", label: "Қосу", Icon: PlusCircle },
];

export default function MusicApp() {
  const [phase, setPhase] = useState<Phase>("loading");

  const bootstrap = useCallback(async () => {
    if (!import.meta.env.DEV && !getInitData()) {
      setPhase("no_telegram");
      return;
    }
    setPhase("loading");
    try {
      await api.auth();
      setPhase("ready");
    } catch (error) {
      setPhase(error instanceof SessionExpiredError ? "session_expired" : "error");
    }
  }, []);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  return (
    <PlayerProvider>
      <LibraryProvider enabled={phase === "ready"}>
        <div className="mx-auto min-h-screen w-full max-w-[1024px] bg-bg pb-[calc(140px+var(--safe-bottom))]">
          <header className="sticky top-0 z-30 flex items-center justify-between border-b border-white/5 bg-bg/80 px-4 py-3 backdrop-blur-xl">
            <Brand product="music" compact />
            <button
              onClick={() => {
                haptic.light();
                navigateApp("cinema");
              }}
              aria-label="Кинотеатрға өту"
              className="ui-switch-entry"
            >
              <Clapperboard size={17} />
              <span>Кино</span>
            </button>
          </header>
          {phase === "loading" && <div className="py-24 text-center text-muted">Жүктелуде…</div>}
          {phase === "error" && <LoadError onRetry={() => void bootstrap()} />}
          {phase === "no_telegram" && <NotInTelegram />}
          {phase === "session_expired" && <SessionExpired />}
          {phase === "ready" && <MusicScreens />}
        </div>
      </LibraryProvider>
    </PlayerProvider>
  );
}

function MusicScreens() {
  const player = usePlayer();
  const [tab, setTab] = useState<Tab>("home");
  const [home, setHome] = useState<MusicHome | null>(null);
  const [homeFailed, setHomeFailed] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [playerOpen, setPlayerOpen] = useState(false);
  const [sheetTrack, setSheetTrack] = useState<Track | null>(null);
  const [pickerTrack, setPickerTrack] = useState<Track | null>(null);
  const [prompt, setPrompt] = useState<Prompt | null>(null);
  const [botSheet, setBotSheet] = useState(false);
  const [sending, setSending] = useState(false);
  const [saving, setSaving] = useState(false);
  const [openPlaylist, setOpenPlaylist] = useState<OpenPlaylist | null>(null);
  const [playlist, setPlaylist] = useState<PlaylistDetail | null>(null);
  const [playlistFailed, setPlaylistFailed] = useState(false);
  const [playlistsVersion, setPlaylistsVersion] = useState(0);
  // Стабильный колбэк: Toast перезапускает таймер на каждый новый onDone, а экран
  // перерисовывается четыре раза в секунду, пока играет музыка.
  const clearToast = useCallback(() => setToast(null), []);

  const loadHome = useCallback(() => {
    setHomeFailed(false);
    musicApi.home().then(setHome, () => setHomeFailed(true));
  }, []);
  useEffect(loadHome, [loadHome]);

  // Ссылка извне: трек (`t_42`) — ставим в плеер и открываем его; плейлист (`pl_код`) —
  // открываем экран чужого плейлиста.
  useEffect(() => {
    const target = musicTarget();
    if (target?.playlistCode) setOpenPlaylist({ code: target.playlistCode });
    if (target?.trackId) {
      musicApi.track(target.trackId).then(
        (track) => {
          player.play([track], 0);
          setPlayerOpen(true);
        },
        () => setToast("Бұл ән табылмады"),
      );
    }
    // Один раз на вход: ссылка — это то, с чем пришли, а не состояние экрана.
  }, []);

  const reloadPlaylist = useCallback(async (target: OpenPlaylist) => {
    setPlaylistFailed(false);
    try {
      setPlaylist("id" in target ? await musicApi.playlist(target.id) : await musicApi.shared(target.code));
    } catch {
      setPlaylistFailed(true);
    }
  }, []);

  useEffect(() => {
    setPlaylist(null);
    if (openPlaylist) void reloadPlaylist(openPlaylist);
  }, [openPlaylist, reloadPlaylist]);

  // Ответ отправки в чат: 409 — чат с ботом не открыт, 503 — Telegram занят.
  const handleSendError = useCallback((error: unknown) => {
    haptic.error();
    if (error instanceof ApiError && error.status === 409) setBotSheet(true);
    else if (error instanceof ApiError && error.status === 503) setToast("Telegram бос емес, сәлден кейін қайталаңыз");
    else setToast("Жіберу мүмкін болмады");
  }, []);

  const sendWith = useCallback(
    async (send: () => Promise<{ count: number }>) => {
      if (sending) return;
      setSending(true);
      try {
        const res = await send();
        haptic.success();
        setToast(res.count > 1 ? `${res.count} ән чатқа жіберілді 🎧` : "Ән чатқа жіберілді 🎧");
      } catch (error) {
        handleSendError(error);
      } finally {
        setSending(false);
      }
    },
    [sending, handleSendError],
  );

  const sendTrack = useCallback((track: Track) => void sendWith(() => musicApi.sendTrack(track.id)), [sendWith]);

  const shareTrack = useCallback((track: Track) => {
    openTelegramLink(shareLink(trackShareUrl(BOT_USERNAME, track.id), `🎧 ${track.performer} — ${track.title}`));
  }, []);

  const addToPlaylist = useCallback(async (target: Playlist | { id: number; title: string }, track: Track) => {
    setPickerTrack(null);
    try {
      const { status } = await musicApi.addToPlaylist(target.id, track.id);
      haptic.success();
      setToast(
        status === "added" ? `«${target.title}» плейлистіне қосылды` :
        status === "duplicate" ? "Бұл ән плейлистте бар" : "Плейлист толы",
      );
      setPlaylistsVersion((v) => v + 1);
    } catch {
      setToast("Қосу мүмкін болмады");
    }
  }, []);

  const submitPrompt = useCallback(
    async (value: string) => {
      if (!prompt) return;
      try {
        if (prompt.kind === "create") {
          const created = await musicApi.createPlaylist(value);
          setPlaylistsVersion((v) => v + 1);
          if (prompt.track) await addToPlaylist(created, prompt.track);
          else setOpenPlaylist({ id: created.id });
        } else if (prompt.kind === "rename") {
          await musicApi.renamePlaylist(prompt.playlist.id, value);
          setPlaylist({ ...prompt.playlist, title: value });
          setPlaylistsVersion((v) => v + 1);
        } else {
          const { votes } = await musicApi.requestTrack(value);
          setToast(votes > 1 ? `Сұраныс қабылданды — сізбен бірге ${votes} адам күтіп жүр` : "Сұраныс қабылданды 🙌");
          loadHome();
        }
        setPrompt(null);
      } catch (error) {
        setToast(error instanceof ApiError && error.code === "playlist_limit" ? "Плейлистер саны шегіне жетті" : "Сақтау мүмкін болмады");
      }
    },
    [prompt, addToPlaylist, loadHome],
  );

  const removeFromPlaylist = useCallback(
    async (track: Track) => {
      if (!playlist?.is_own) return;
      try {
        await musicApi.removeFromPlaylist(playlist.id, track.id);
        setPlaylist({ ...playlist, tracks: playlist.tracks.filter((t) => t.id !== track.id), track_count: playlist.track_count - 1 });
        setPlaylistsVersion((v) => v + 1);
      } catch {
        setToast("Алып тастау мүмкін болмады");
      }
    },
    [playlist],
  );

  const deletePlaylist = useCallback(async () => {
    if (!playlist?.is_own) return;
    if (!window.confirm(`«${playlist.title}» плейлисін жою керек пе?`)) return;
    try {
      await musicApi.deletePlaylist(playlist.id);
      setOpenPlaylist(null);
      setPlaylistsVersion((v) => v + 1);
      setToast("Плейлист жойылды");
    } catch {
      setToast("Жою мүмкін болмады");
    }
  }, [playlist]);

  const saveShared = useCallback(async () => {
    if (!openPlaylist || !("code" in openPlaylist)) return;
    setSaving(true);
    try {
      const saved = await musicApi.saveShared(openPlaylist.code);
      haptic.success();
      setToast("Плейлист сізде сақталды");
      setPlaylistsVersion((v) => v + 1);
      setOpenPlaylist({ id: saved.id });
    } catch {
      setToast("Сақтау мүмкін болмады");
    } finally {
      setSaving(false);
    }
  }, [openPlaylist]);

  const sendPlaylist = useCallback(() => {
    if (!playlist || !openPlaylist) return;
    void sendWith(() => ("code" in openPlaylist ? musicApi.sendShared(openPlaylist.code) : musicApi.sendPlaylist(playlist.id)));
  }, [playlist, openPlaylist, sendWith]);

  // «Назад» Telegram закрывает верхний оверлей.
  const overlayOpen = Boolean(sheetTrack || pickerTrack || prompt || botSheet || playerOpen || openPlaylist);
  const closeTop = useCallback(() => {
    if (botSheet) setBotSheet(false);
    else if (prompt) setPrompt(null);
    else if (pickerTrack) setPickerTrack(null);
    else if (sheetTrack) setSheetTrack(null);
    else if (playerOpen) setPlayerOpen(false);
    else if (openPlaylist) setOpenPlaylist(null);
  }, [botSheet, prompt, pickerTrack, sheetTrack, playerOpen, openPlaylist]);
  useTelegramBackButton(overlayOpen, closeTop);

  return (
    <>
      {tab === "home" && (
        <HomeView
          home={home}
          failed={homeFailed}
          onRetry={loadHome}
          onMore={setSheetTrack}
          onRequest={(query) => setPrompt({ kind: "request", initial: query })}
          onAdd={() => setTab("add")}
        />
      )}
      {tab === "library" && (
        <LibraryView
          onMore={setSheetTrack}
          onOpenPlaylist={(p) => setOpenPlaylist({ id: p.id })}
          onCreatePlaylist={() => setPrompt({ kind: "create", track: null })}
          onSendAll={() => void sendWith(() => musicApi.sendLibrary())}
          sending={sending}
          playlistsVersion={playlistsVersion}
          onBrowse={() => setTab("home")}
        />
      )}
      {tab === "add" && <AddView requests={home?.requests ?? []} onRequest={() => setPrompt({ kind: "request", initial: "" })} />}

      {openPlaylist && (
        <PlaylistScreen
          playlist={playlist}
          failed={playlistFailed}
          sending={sending}
          saving={saving}
          onBack={() => setOpenPlaylist(null)}
          onMore={setSheetTrack}
          onSend={sendPlaylist}
          onShare={() => playlist && openTelegramLink(shareLink(playlist.share_url, `🎧 «${playlist.title}» плейлисі`))}
          onRename={() => playlist && setPrompt({ kind: "rename", playlist })}
          onDelete={() => void deletePlaylist()}
          onSave={() => void saveShared()}
        />
      )}

      {!playerOpen && <MiniPlayer onOpen={() => setPlayerOpen(true)} />}

      <nav className="fixed inset-x-0 bottom-0 z-[36] mx-auto flex max-w-[1024px] border-t border-white/5 bg-bg/90 pb-[var(--safe-bottom)] backdrop-blur-xl">
        {TABS.map(({ id, label, Icon }) => {
          const active = tab === id && !openPlaylist;
          return (
            <button
              key={id}
              onClick={() => {
                haptic.light();
                setOpenPlaylist(null);
                setTab(id);
                window.scrollTo({ top: 0 });
              }}
              aria-current={active ? "page" : undefined}
              className={`flex flex-1 flex-col items-center gap-1 py-2.5 transition-colors ${active ? "text-music" : "text-faint active:text-muted"}`}
            >
              <Icon size={23} strokeWidth={active ? 2.4 : 2} />
              <span className="text-[11px] font-medium leading-none">{label}</span>
            </button>
          );
        })}
      </nav>

      {playerOpen && (
        <FullPlayer onClose={() => setPlayerOpen(false)} onSend={sendTrack} onMore={setSheetTrack} sending={sending} />
      )}

      <TrackSheet
        track={sheetTrack}
        onClose={() => setSheetTrack(null)}
        onSend={sendTrack}
        onAddToPlaylist={setPickerTrack}
        onShare={shareTrack}
        onRemove={openPlaylist && playlist?.is_own && !playerOpen ? (track) => void removeFromPlaylist(track) : undefined}
      />
      <PlaylistPicker
        track={pickerTrack}
        onClose={() => setPickerTrack(null)}
        onPick={(target, track) => void addToPlaylist(target, track)}
        onCreate={(track) => {
          setPickerTrack(null);
          setPrompt({ kind: "create", track });
        }}
      />
      <TextPrompt
        open={prompt !== null}
        title={prompt?.kind === "rename" ? "Атын өзгерту" : prompt?.kind === "request" ? "Ән сұрау" : "Жаңа плейлист"}
        hint={prompt?.kind === "request" ? "Әннің атын және орындаушысын жазыңыз. Әні бар адам оны ботқа жібереді." : undefined}
        placeholder={prompt?.kind === "request" ? "Мысалы: Қайрат Нұртас — Ауру" : "Мысалы: Жолға"}
        initial={prompt?.kind === "rename" ? prompt.playlist.title : prompt?.kind === "request" ? prompt.initial : ""}
        submitLabel={prompt?.kind === "request" ? "Сұрау" : "Сақтау"}
        maxLength={prompt?.kind === "request" ? 120 : 64}
        onSubmit={submitPrompt}
        onClose={() => setPrompt(null)}
      />
      <BotStartSheet open={botSheet} onClose={() => setBotSheet(false)} subject="music" />
      {toast && <Toast message={toast} onDone={clearToast} />}
    </>
  );
}
