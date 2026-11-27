// QazaqMusic — музыкальный раздел Mini App.
//
// Устроен как кинотеатр: сервер музыку не хранит и не стримит, «тыңдау» — это треки в чате
// с ботом, где их по порядку играет плеер Telegram (в том числе с выключенным экраном).
// Поэтому «Ойнату» у плейлиста отправляет весь список, а тап по треку внутри списка — он
// и всё, что после него. Раздел бесплатный: ни пэйволла, ни подарков.
//
// Оверлеи живут стеком, и нативная кнопка «назад» Telegram закрывает верхний из них.

import { useCallback, useEffect, useState } from "react";

import { Clapperboard, Home, Library, PlusCircle, User, type LucideIcon } from "../ui-kit/adapters/icons";

import BotStartSheet from "../components/BotStartSheet";
import { LoadError, NotInTelegram, SessionExpired } from "../components/States";
import Toast from "../components/Toast";
import { useTelegramBackButton } from "../hooks/useTelegramBackButton";
import { ApiError, api, SessionExpiredError } from "../lib/api";
import { BOT_USERNAME, getInitData, haptic, openTelegramLink } from "../lib/telegram";
import { Brand } from "../ui-kit";
import AddView from "./AddView";
import { musicApi, type Collection, type MusicHome, type Playlist, type PlaylistDetail, type Track, type TrackDetail } from "./api";
import PlaylistPicker from "./components/PlaylistPicker";
import SentBar from "./components/SentBar";
import TextPrompt from "./components/TextPrompt";
import TrackSheet from "./components/TrackSheet";
import HomeView, { COLLECTION_ICONS } from "./HomeView";
import { musicTarget, navigateApp, shareLink, trackShareUrl } from "./launch";
import LibraryView from "./LibraryView";
import ListScreen, { type ListData } from "./ListScreen";
import TrackScreen from "./TrackScreen";
import { LibraryProvider } from "./useLibrary";

type Tab = "home" | "library" | "add";
type Phase = "loading" | "ready" | "error" | "no_telegram" | "session_expired";

type Prompt =
  | { kind: "create"; track: Track | null }
  | { kind: "rename"; playlist: PlaylistDetail }
  | { kind: "request"; initial: string };

/** Что открыто поверх вкладок: свой плейлист, чужой по коду или готовая подборка. */
type OpenList =
  | { kind: "own"; id: number }
  | { kind: "shared"; code: string }
  | { kind: "collection"; key: string }
  | { kind: "artist"; slug: string };

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
    <LibraryProvider enabled={phase === "ready"}>
      <div className="mx-auto min-h-screen w-full max-w-[1024px] bg-bg pb-[calc(90px+var(--safe-bottom))]">
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
  );
}

function MusicScreens() {
  const [tab, setTab] = useState<Tab>("home");
  const [home, setHome] = useState<MusicHome | null>(null);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [publicPlaylists, setPublicPlaylists] = useState<Playlist[]>([]);
  const [homeFailed, setHomeFailed] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [sentCount, setSentCount] = useState<number | null>(null);
  const [sheetTrack, setSheetTrack] = useState<Track | null>(null);
  const [pickerTrack, setPickerTrack] = useState<Track | null>(null);
  const [prompt, setPrompt] = useState<Prompt | null>(null);
  const [botSheet, setBotSheet] = useState(false);
  const [sending, setSending] = useState(false);
  const [saving, setSaving] = useState(false);
  const [openList, setOpenList] = useState<OpenList | null>(null);
  const [list, setList] = useState<ListData | null>(null);
  const [playlist, setPlaylist] = useState<PlaylistDetail | null>(null);
  const [listFailed, setListFailed] = useState(false);
  const [playlistsVersion, setPlaylistsVersion] = useState(0);
  const [openTrack, setOpenTrack] = useState<number | null>(null);
  const [trackDetail, setTrackDetail] = useState<TrackDetail | null>(null);
  const [trackFailed, setTrackFailed] = useState(false);
  const clearToast = useCallback(() => setToast(null), []);
  const clearSent = useCallback(() => setSentCount(null), []);

  const loadHome = useCallback(() => {
    setHomeFailed(false);
    musicApi.home().then(setHome, () => setHomeFailed(true));
    musicApi.collections().then(setCollections, () => {});
    musicApi.publicPlaylists().then(setPublicPlaylists, () => {});
  }, []);
  useEffect(loadHome, [loadHome]);

  // Ссылка извне: трек (`t_42`) — сразу в чат не шлём (человек ещё не нажимал), а
  // открываем его страницу; плейлист (`pl_код`) — экран чужого плейлиста.
  useEffect(() => {
    const target = musicTarget();
    if (target?.playlistCode) setOpenList({ kind: "shared", code: target.playlistCode });
    if (target?.trackId) setOpenTrack(target.trackId);
  }, []);

  useEffect(() => {
    setTrackDetail(null);
    setTrackFailed(false);
    if (openTrack === null) return;
    musicApi.trackDetails(openTrack).then(setTrackDetail, () => setTrackFailed(true));
  }, [openTrack]);

  const loadList = useCallback(async (target: OpenList) => {
    setListFailed(false);
    try {
      if (target.kind === "artist") {
        const found = await musicApi.artist(target.slug);
        setPlaylist(null);
        setList({ kind: "collection", title: found.name, subtitle: "орындаушы", tracks: found.tracks, Icon: User });
        return;
      }
      if (target.kind === "collection") {
        const found = await musicApi.collection(target.key);
        setPlaylist(null);
        setList({ kind: "collection", title: found.title, subtitle: found.subtitle, tracks: found.tracks, Icon: COLLECTION_ICONS[found.key] });
        return;
      }
      const found = target.kind === "own" ? await musicApi.playlist(target.id) : await musicApi.shared(target.code);
      setPlaylist(found);
      setList({
        kind: found.is_own ? "own" : "shared",
        title: found.title,
        subtitle: found.is_own ? "" : "тыңдаушы плейлисі",
        tracks: found.tracks,
        isPublic: found.is_public,
      });
    } catch {
      setListFailed(true);
    }
  }, []);

  useEffect(() => {
    setList(null);
    setPlaylist(null);
    if (openList) void loadList(openList);
  }, [openList, loadList]);

  const send = useCallback(
    async (tracks: Track[]) => {
      if (sending || tracks.length === 0) return;
      setSending(true);
      try {
        const res = await musicApi.send(tracks.map((t) => t.id));
        haptic.success();
        setSentCount(res.count);
      } catch (error) {
        haptic.error();
        if (error instanceof ApiError && error.status === 409) setBotSheet(true);
        else if (error instanceof ApiError && error.status === 503) setToast("Telegram бос емес, сәлден кейін қайталаңыз");
        else setToast("Жіберу мүмкін болмады");
      } finally {
        setSending(false);
      }
    },
    [sending],
  );

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
          else setOpenList({ kind: "own", id: created.id });
        } else if (prompt.kind === "rename") {
          await musicApi.updatePlaylist(prompt.playlist.id, { title: value });
          setPlaylist({ ...prompt.playlist, title: value });
          setList((prev) => (prev ? { ...prev, title: value } : prev));
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
        const tracks = playlist.tracks.filter((t) => t.id !== track.id);
        setPlaylist({ ...playlist, tracks, track_count: tracks.length });
        setList((prev) => (prev ? { ...prev, tracks } : prev));
        setPlaylistsVersion((v) => v + 1);
      } catch {
        setToast("Алып тастау мүмкін болмады");
      }
    },
    [playlist],
  );

  const reorder = useCallback(
    async (tracks: Track[]) => {
      if (!playlist?.is_own) return false;
      try {
        await musicApi.reorderPlaylist(playlist.id, tracks.map((t) => t.id));
        setPlaylist({ ...playlist, tracks });
        setList((prev) => (prev ? { ...prev, tracks } : prev));
        haptic.success();
        setToast("Реті сақталды");
        return true;
      } catch {
        // Плейлист изменился в другом месте — перечитываем, чтобы не потерять треки.
        setToast("Плейлист өзгерген, қайта ашылды");
        if (openList) void loadList(openList);
        return true;
      }
    },
    [playlist, openList, loadList],
  );

  const togglePublic = useCallback(
    async (value: boolean) => {
      if (!playlist?.is_own) return;
      setList((prev) => (prev ? { ...prev, isPublic: value } : prev));
      try {
        await musicApi.updatePlaylist(playlist.id, { is_public: value });
        setPlaylist({ ...playlist, is_public: value });
        setToast(value ? "Енді плейлистті бәрі көреді 🌍" : "Плейлист тек сілтеме арқылы ашылады");
        musicApi.publicPlaylists().then(setPublicPlaylists, () => {});
      } catch {
        setList((prev) => (prev ? { ...prev, isPublic: !value } : prev));
        setToast("Сақтау мүмкін болмады");
      }
    },
    [playlist],
  );

  const deletePlaylist = useCallback(async () => {
    if (!playlist?.is_own) return;
    if (!window.confirm(`«${playlist.title}» плейлисін жою керек пе?`)) return;
    try {
      await musicApi.deletePlaylist(playlist.id);
      setOpenList(null);
      setPlaylistsVersion((v) => v + 1);
      setToast("Плейлист жойылды");
    } catch {
      setToast("Жою мүмкін болмады");
    }
  }, [playlist]);

  // «Өзіме сақтау»: чужой плейлист копируется на сервере, подборка — списком треков.
  const saveList = useCallback(async () => {
    if (!openList || !list) return;
    setSaving(true);
    try {
      const saved =
        openList.kind === "shared"
          ? await musicApi.saveShared(openList.code)
          : await musicApi.createPlaylist(list.title, list.tracks.map((t) => t.id));
      haptic.success();
      setToast("Плейлист сізде сақталды");
      setPlaylistsVersion((v) => v + 1);
      setOpenList({ kind: "own", id: saved.id });
    } catch (error) {
      setToast(error instanceof ApiError && error.code === "playlist_limit" ? "Плейлистер саны шегіне жетті" : "Сақтау мүмкін болмады");
    } finally {
      setSaving(false);
    }
  }, [openList, list]);

  const sharePlaylist = useCallback(() => {
    if (playlist) openTelegramLink(shareLink(playlist.share_url, `🎧 «${playlist.title}» плейлисі`));
  }, [playlist]);

  // «Назад» Telegram закрывает верхний оверлей.
  const overlayOpen = Boolean(sheetTrack || pickerTrack || prompt || botSheet || openList || openTrack);
  const closeTop = useCallback(() => {
    if (botSheet) setBotSheet(false);
    else if (prompt) setPrompt(null);
    else if (pickerTrack) setPickerTrack(null);
    else if (sheetTrack) setSheetTrack(null);
    else if (openTrack !== null) setOpenTrack(null);
    else if (openList) setOpenList(null);
  }, [botSheet, prompt, pickerTrack, sheetTrack, openTrack, openList]);
  useTelegramBackButton(overlayOpen, closeTop);

  return (
    <>
      {tab === "home" && (
        <HomeView
          home={home}
          collections={collections}
          publicPlaylists={publicPlaylists}
          failed={homeFailed}
          busy={sending}
          onRetry={loadHome}
          onSend={(tracks) => void send(tracks)}
          onMore={setSheetTrack}
          onOpenCollection={(c) => setOpenList({ kind: "collection", key: c.key })}
          onOpenPlaylist={(p) => setOpenList(p.is_own ? { kind: "own", id: p.id } : { kind: "shared", code: p.share_code })}
          onRequest={(query) => setPrompt({ kind: "request", initial: query })}
          onAdd={() => setTab("add")}
        />
      )}
      {tab === "library" && (
        <LibraryView
          onMore={setSheetTrack}
          onOpenPlaylist={(p) => setOpenList({ kind: "own", id: p.id })}
          onCreatePlaylist={() => setPrompt({ kind: "create", track: null })}
          onSend={(tracks) => void send(tracks)}
          busy={sending}
          playlistsVersion={playlistsVersion}
          onBrowse={() => setTab("home")}
          onAdd={() => setTab("add")}
        />
      )}
      {tab === "add" && <AddView requests={home?.requests ?? []} onRequest={() => setPrompt({ kind: "request", initial: "" })} />}

      {openList && (
        <ListScreen
          data={list}
          failed={listFailed}
          busy={sending}
          saving={saving}
          onBack={() => setOpenList(null)}
          onSend={(tracks) => void send(tracks)}
          onMore={setSheetTrack}
          onShare={playlist ? sharePlaylist : undefined}
          onRename={playlist?.is_own ? () => setPrompt({ kind: "rename", playlist }) : undefined}
          onDelete={playlist?.is_own ? () => void deletePlaylist() : undefined}
          onSave={list && list.kind !== "own" ? () => void saveList() : undefined}
          onTogglePublic={playlist?.is_own ? (value) => void togglePublic(value) : undefined}
          onReorder={playlist?.is_own ? reorder : undefined}
        />
      )}

      {openTrack !== null && (
        <TrackScreen
          detail={trackDetail}
          failed={trackFailed}
          busy={sending}
          onBack={() => setOpenTrack(null)}
          onSend={(tracks) => void send(tracks)}
          onMore={setSheetTrack}
          onAddToPlaylist={setPickerTrack}
          onShare={shareTrack}
          onOpenArtist={(slug) => {
            setOpenTrack(null);
            setOpenList({ kind: "artist", slug });
          }}
          onOpenPlaylist={(p) => {
            setOpenTrack(null);
            setOpenList(p.is_own ? { kind: "own", id: p.id } : { kind: "shared", code: p.share_code });
          }}
        />
      )}

      <nav className="fixed inset-x-0 bottom-0 z-[38] mx-auto flex max-w-[1024px] border-t border-white/5 bg-bg/90 pb-[var(--safe-bottom)] backdrop-blur-xl">
        {TABS.map(({ id, label, Icon }) => {
          const active = tab === id && !openList;
          return (
            <button
              key={id}
              onClick={() => {
                haptic.light();
                setOpenList(null);
                setOpenTrack(null);
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

      {sentCount !== null && <SentBar count={sentCount} onClose={clearSent} />}

      <TrackSheet
        track={sheetTrack}
        onClose={() => setSheetTrack(null)}
        onSend={(track) => void send([track])}
        onAddToPlaylist={setPickerTrack}
        onShare={shareTrack}
        onAbout={(track) => setOpenTrack(track.id)}
        onRemove={openList?.kind === "own" && playlist?.is_own ? (track) => void removeFromPlaylist(track) : undefined}
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
