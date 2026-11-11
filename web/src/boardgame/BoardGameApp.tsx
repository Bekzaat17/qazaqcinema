import TradeOffers from "./components/TradeOffers";
import RoomExplorer from "./components/RoomExplorer";
import GameRecords from "./components/GameRecords";
import AssetStrip from "./components/AssetStrip";
import GameChannelGate from "./components/GameChannelGate";
import { roomCode, roomLink, shareRoomLink } from "./rooms";
import PlayerAvatar, { type Portrait } from "../ui-kit/PlayerAvatar";
import { playerAppearance, savedPortrait, savePortrait, telegramAvatar } from "./appearance";
import AppearancePicker from "./components/AppearancePicker";
import { GameCoin } from "../ui-kit/GameIcons";
import CoinAmount from "./components/CoinAmount";
import { Brand } from "../ui-kit";
import Dice from "./components/Dice";
import PropertyPanel from "./components/PropertyPanel";
import HomeScreen from "./components/HomeScreen";
import LobbyScreen from "./components/LobbyScreen";
import { gameText, money } from "./format";
import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import {
  ArrowRight,
  Clapperboard,
  ChevronRight,
  Crown,
  Dices,
  HandCoins,
  HelpCircle,
  Landmark,
  MapPin,
  RotateCcw,
  ScrollText,
  ShoppingBag,
  Trophy,
  Users,
  X,
  ZoomIn,
  ZoomOut,
  History,
  Globe2,
  LockKeyhole,
} from "../ui-kit/adapters/icons";
import { ApiError, NetworkError, SessionExpiredError } from "../lib/api";
import {
  BOT_URL,
  getInitData,
  getTelegramUser,
  getWebApp,
  haptic,
  openTelegramLink,
  showBackButton,
} from "../lib/telegram";
import { navigateApp } from "../quest/launch";
import QuestDialog from "../quest/components/QuestDialog";
import {
  HttpGameGateway,
  LIVE_ROOM_KEY,
  PracticeGameGateway,
  type GameGateway,
} from "./gateway";
import { activeCatalog, boardFor, netWorth, rentFor, offerRecipient } from "./rules";
import type { BoardWorld } from "./world";
import IllustratedBoard from "./components/IllustratedBoard";
import LocationArtwork from "./components/LocationArtwork";
import type { Action, Catalog, Command, RoomView, Scenario } from "./types";
import "./boardgame.css";

const Learning = lazy(() => import("../quest/QuestApp"));
const MESSAGES: Record<string, string> = {
  channel_required: "Келесі партия үшін арнаға жазылуыңды раста.",
  stale: "Бөлме жаңарды. Ағымдағы күй көрсетілді — әрекетті қайта таңда.",
  forbidden: "Қазір бұл әрекетті орындау құқығың жоқ.",
  invalid: "Бұл әрекет қазір қолжетімсіз.",
  insufficient: "Dala монетасы жеткіліксіз.",
  group_required:
    "Алдымен осы түстегі барлық кәсіпті сатып ал. Кепілдегі кәсіптерді қайтар.",
  even_building: "Түсті топтағы ғимараттарды біркелкі дамыт немесе сат.",
  sell_first: "Алдымен осы топтағы барлық ғимаратты сат.",
  not_ready: "Кемінде екі қатысушы керек және адамдар дайын болуы тиіс.",
  full: "Бөлмедегі төрт орын толды.",
  bot_declined:
    "Бот ұсынысты қабылдамады. Сатып алсаң — кемінде 150%; сатсаң — ең көбі бастапқы бағаның 2/3 бөлігі.",
  too_early: "Бұл қатысушының жүріс уақыты әлі аяқталған жоқ.",
};
function errorText(error: unknown) {
  if (error instanceof SessionExpiredError)
    return "Сессия аяқталды. Ойынды Telegram-нан қайта аш.";
  if (error instanceof NetworkError)
    return "Байланыс үзілді. Әрекетті қауіпсіз қайталауға болады.";
  if (error instanceof ApiError)
    return (
      (
        {
          room_not_found: "Бөлме табылмады немесе оған қосылмағансың.",
          room_full: "Бөлме толды. Хосттан боттың орнын босатуды сұра.",
          room_not_available: "Бөлме табылмады немесе партия басталып кеткен.",
          too_many_requests: "Бір сәт күте тұр да, қайталап көр.",
        } as Record<string, string>
      )[error.code] ?? "Сақтау қызметі уақытша қолжетімсіз."
    );
  return "Ойын жүктелмеді. Байланысты тексеріп, қайта көр.";
}

function invitation(): string {
  const value =
    new URLSearchParams(window.location.search).get("room") ??
    getWebApp()?.initDataUnsafe?.start_param?.replace(/^quest_room_/, "") ??
    new URLSearchParams(window.location.search)
      .get("tgWebAppStartParam")
      ?.replace(/^quest_room_/, "") ??
    "";
  return /^[a-f0-9]{10}$/i.test(value) ? value.toUpperCase() : "";
}
const startIntent = () => getWebApp()?.initDataUnsafe?.start_param
  ?? new URLSearchParams(window.location.search).get("tgWebAppStartParam");
type Panel =
  | "channel"
  | "rooms"
  | "create"
  | "history"
  | "help"
  | "ranking"
  | "join"
  | "property"
  | "assets"
  | "offers"
  | "journal"
  | "leave"
  | "new"
  | "result"
  | "telegram"
  | null;

export default function BoardGameApp() {
  const [catalog, setCatalog] = useState<Catalog | null>(null),
    [gateway, setGateway] = useState<GameGateway | null>(null),
    [view, setView] = useState<RoomView | null>(null),
    [screen, setScreen] = useState<"home" | "room">("home"),
    [boardId, setBoardId] = useState("almaty"),
    [scenarioId, setScenarioId] = useState("almaty_first"),
    [name, setName] = useState(() => (getTelegramUser()?.first_name || "Саяхатшы").slice(0, 24)),
    [isPublic, setIsPublic] = useState(() => startIntent() === "quest_create_public"),
    [code, setCode] = useState(invitation),
    [panel, setPanel] = useState<Panel>(null),
    [selected, setSelected] = useState(-1),
    [assetsPlayer, setAssetsPlayer] = useState(0),
    [busy, setBusy] = useState(false),
    [animating, setAnimating] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [worldError, setWorldError] = useState(false),
    [connection, setConnection] = useState(true),
    [reload, setReload] = useState(0),
    [learning, setLearning] = useState(false),
    [clock, setClock] = useState(Date.now());
  const [viewMode, setViewMode] = useState<"illustrated" | "3d">("illustrated");
  const [mapZoom, setMapZoom] = useState(1);
  const [portrait, setPortrait] = useState<Portrait>(savedPortrait);
  const appearance = { avatar_url: telegramAvatar(getTelegramUser()?.photo_url), portrait };
  const choosePortrait = (value: Portrait) => { setPortrait(value); savePortrait(value); };
  const [mapRotation, setMapRotation] = useState(0);
  const [worldVersion, setWorldVersion] = useState(0);
  const host = useRef<HTMLDivElement>(null),
    world = useRef<BoardWorld | null>(null),
    inFlight = useRef(false),
    pick = useRef<(index: number) => void>(() => {}),
    retry = useRef<() => Promise<void>>(() => Promise.resolve()),
    mounted = useRef(true),
    latest = useRef<RoomView | null>(null),
    pendingNew = useRef<Scenario | null>(null),
    serverOffset = useRef(0);
  const selectMapTile = useCallback((index: number) => pick.current(index), []);
  const room = view?.room ?? null,
    match = room?.match ?? null,
    me = match?.players.findIndex((p) => p.id === view?.me) ?? -1,
    myTurn = !!match && me === match.turn && !match.players[me]?.bankrupt;
  const board = catalog
    ? screen === "room" && room
      ? boardFor(catalog, room)
      : (catalog.boards.find((b) => b.id === boardId) ?? catalog.boards[0])
    : null;
  const appearances = view ? {
    ...view.appearances,
    [view.me]: view.appearances?.[view.me] ?? appearance,
  } : undefined;
  const scenario = (catalog && screen === "room" && room ? activeCatalog(catalog, room) : catalog)?.scenarios.find(
    (s) => s.id === (screen === "room" && room ? room.scenario_id : scenarioId),
  );
  const disabled = busy || animating;
  const setRoom = useCallback((next: RoomView) => {
    const previous = latest.current;
    if (
      previous &&
      next.code === previous.code &&
      next.room.revision < previous.room.revision
    )
      return;
    latest.current = next;
    serverOffset.current = new Date(next.server_time).getTime() - Date.now();
    setView(next);
    setConnection(true);
    if (next.outcome !== "applied")
      setNotice(MESSAGES[next.outcome] ?? "Қайта көр.");
    if (next.outcome === "channel_required") {
      if (next.blocked_seats?.includes(next.me)) setPanel("channel");
      else setNotice(`${next.room.seats.filter((s) => next.blocked_seats?.includes(s.id)).map((s) => s.name).join(", ")}: ойынды жалғастыру үшін арнаға жазылуы керек.`);
    }
    if (
      next.room.match?.phase === "buy" &&
      next.room.match.players[next.room.match.turn].id === next.me
    )
      setSelected(next.room.match.pending);
    if (
      next.room.match?.phase === "finished" &&
      previous?.room.match?.phase !== "finished"
    )
      setPanel("result");
  }, []);
  pick.current = (index) => {
    if (screen === "room" && match) {
      setSelected(index);
      setPanel("property");
    }
  };
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    let active = true;
    setError("");
    void (async () => {
      try {
        const response = await fetch(
          getInitData() ? "/api/boardgame/catalog" : "/boardgame/catalog.json",
        );
        if (!response.ok) throw new Error("catalog");
        const definitions = (await response.json()) as Catalog;
        if (!active) return;
        const client = getInitData()
          ? new HttpGameGateway()
          : new PracticeGameGateway(definitions);
        setCatalog(definitions);
        setGateway(client);
        setScenarioId(definitions.scenarios[0].id);
        setBoardId(definitions.boards[0].id);
        try {
          let saved = "";
          try {
            saved = client.practice
              ? "PRACTICE"
              : (localStorage.getItem(LIVE_ROOM_KEY) ?? "");
          } catch {
            /* Запрет localStorage не мешает новой партии. */
          }
          if (saved) {
            const restored = await client.view(saved);
            if (active) {
              setRoom(restored);
              setScreen("room");
            }
          }
        } catch {
          /* Отсутствующая локальная партия — обычный первый вход. */
        }
        if (active && invitation()) setPanel("join");
        else if (active) {
          const intent = startIntent();
          if (intent === "quest_rooms") setPanel("rooms");
          else if (intent?.startsWith("quest_create")) setPanel("create");
        }
      } catch (e) {
        if (active) setError(errorText(e));
      }
    })();
    return () => {
      active = false;
    };
  }, [reload, setRoom]);
  useEffect(() => {
    if (!catalog || learning || viewMode !== "3d") return;
    let active = true;
    setWorldError(false);
    void import("./world")
      .then(({ BoardWorld }) => {
        if (!active || !host.current) return;
        try {
          world.current = new BoardWorld(
            host.current,
            (index) => pick.current(index),
            setAnimating,
            () => setWorldError(true),
          );
          setWorldVersion((value) => value + 1);
        } catch {
          setWorldError(true);
        }
      })
      .catch(() => {
        if (active) setWorldError(true);
      });
    return () => {
      active = false;
      world.current?.dispose();
      world.current = null;
      setAnimating(false);
    };
  }, [catalog, learning, viewMode]);
  useEffect(() => {
    if (board) {
      world.current?.setBoard(board);
      world.current?.update(
        screen === "room" ? match : null,
        screen === "home",
      );
      world.current?.setSelection(screen === "room" ? selected : -1);
    }
  }, [board, match, screen, selected, learning, worldVersion]);
  useEffect(() => {
    world.current?.pause((panel !== null && !animating) || learning);
  }, [panel, learning, catalog, animating]);
  useEffect(() => {
    if (!gateway || gateway.practice || !view) return;
    const controller = new AbortController();
    let stopped = false;
    void (async () => {
      while (!stopped) {
        try {
          const revision = latest.current?.room.revision;
          const next = await gateway.view(
            view.code,
            revision,
            controller.signal,
          );
          if (!stopped) setRoom(next);
        } catch {
          if (stopped) break;
          setConnection(false);
          await new Promise<void>((resolve) => {
            const finish = () => {
              clearTimeout(timer);
              controller.signal.removeEventListener("abort", finish);
              resolve();
            };
            const timer = setTimeout(finish, 4000);
            controller.signal.addEventListener("abort", finish, { once: true });
            if (controller.signal.aborted) finish();
          });
        }
      }
    })();
    return () => {
      stopped = true;
      controller.abort();
    };
  }, [gateway, view?.code, setRoom]);
  useEffect(() => {
    const timer = setInterval(() => setClock(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    const title = document.title;
    document.title = "QazaqPlay — Дала дәулеті";
    return () => {
      document.title = title;
    };
  }, []);
  useEffect(() => {
    if (!getInitData() || learning) return;
    return showBackButton(() => {
      if (inFlight.current) return;
      if (panel) setPanel(null);
      else if (screen === "room") setScreen("home");
      else navigateApp("cinema");
    });
  }, [panel, screen, learning]);
  const perform = useCallback(async (operation: () => Promise<void>) => {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    retry.current = operation;
    try {
      await operation();
    } catch (e) {
      if (mounted.current) setError(errorText(e));
    } finally {
      if (mounted.current) setBusy(false);
      inFlight.current = false;
    }
  }, []);
  const send = (kind: Action, target = "", tile = -1, amount = 0, giveTile = -1) => {
    if (!gateway || !view) return;
    const command: Command = {
      revision: view.room.revision,
      kind,
      target,
      tile,
      amount,
      give_tile: giveTile,
    };
    void perform(async () => {
      const next = await gateway.act(view.code, command);
      setRoom(next);
      if (next.outcome === "applied") {
        haptic.light();
        if (["offer", "ask", "counter"].includes(kind)) {
          const pending = next.room.match?.offers.some((o) => (o.proposer ?? o.buyer) === me);
          if (pending) setPanel("offers");
          setNotice(pending ? "Ұсыныс жіберілді. Жауап күтеміз." : "Мәміле аяқталды.");
        }
      }
    });
  };
  useEffect(() => {
    if (!gateway || !view || inFlight.current) return;
    let active = true;
    void gateway.setAppearance(view.code, appearance).then((next) => {
      if (active) setRoom(next);
    }).catch(() => {
      if (active) setNotice("Бейнең сақталмады. Байланыс қалпына келгенде қайта кір.");
    });
    return () => { active = false; };
    // Метаданные обновляются при входе или выборе портрета, не при каждом ходе.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gateway, view?.code, appearance.avatar_url, appearance.portrait, setRoom]);
  useEffect(() => {
    if (!gateway || !view || view.room.match) return;
    let active = true;
    void gateway.access().then((status) => { if (active && !status.allowed) setPanel("channel"); }).catch(() => {});
    return () => { active = false; };
  }, [gateway, view?.code, !!view?.room.match]);
  const create = (next: Scenario) => {
    if (!gateway) return;
    void perform(async () => {
      const created = await gateway.create(name.trim() || "Саяхатшы", next.id, appearance, isPublic);
      setRoom(created);
      setScreen("room");
      setPanel(null);
      setSelected(-1);
      try {
        if (!gateway.practice)
          localStorage.setItem(LIVE_ROOM_KEY, created.code);
      } catch {
        /* Комната доступна и без локального восстановления. */
      }
    });
  };
  const requestCreate = () => {
    if (!scenario) return;
    if (room?.match && room.match.phase !== "finished") {
      pendingNew.current = scenario;
      setPanel("new");
    } else create(scenario);
  };
  const join = (providedCode = roomCode(code)) => {
    if (!gateway) return;
    if (!providedCode) return;
    if (gateway.practice) {
      openTelegramLink(roomLink(BOT_URL, providedCode));
      return;
    }
    void perform(async () => {
      const joined = await gateway.join(
        name.trim() || "Саяхатшы",
        providedCode,
        appearance,
      );
      setRoom(joined);
      setScreen("room");
      setPanel(null);
      try {
        localStorage.setItem(LIVE_ROOM_KEY, joined.code);
      } catch {
        /* Ссылка остаётся пригодной для входа. */
      }
    });
  };
  const close = () => {
    if (!busy) {
      setPanel(null);
      setNotice("");
    }
  };
  const copyText = async (text: string, success: string) => {
    try {
      if (!navigator.clipboard) throw new Error("clipboard_unavailable");
      await navigator.clipboard.writeText(text);
      setNotice(success);
    } catch { setNotice("Кодты немесе сілтемені белгілеп, қолмен көшір."); }
  };
  const copyInvite = () => { if (view) void copyText(roomLink(BOT_URL, view.code), "Сілтеме көшірілді. Досыңа жібер."); };
  if (learning)
    return (
      <Suspense fallback={<p role="status">Ауылың жүктелуде…</p>}>
        <Learning onReturn={() => setLearning(false)} />
      </Suspense>
    );
  const selectedTile = selected >= 0 ? board?.tiles[selected] : null,
    selectedLot = match?.lots[selected],
    owner = selectedLot ? match?.players[selectedLot.owner] : null;
  const inbox = match?.offers.filter((o) => offerRecipient(o) === me) ?? [];
  const player = match && me >= 0 ? match.players[me] : null;
  const deadline = view?.deadline ? new Date(view.deadline).getTime() : null;
  const canTimeout =
    deadline !== null && clock >= deadline - serverOffset.current;
  return (
    <main
      className={`dala-app ${screen === "room" ? "dala-in-room" : "dala-home"}`}
    >
      <div className="dala-universe" aria-hidden="true" />
      <div
        className={`dala-world ${viewMode === "illustrated" ? "is-illustrated" : ""}`}
        ref={host}
        inert={screen === "room" && !match ? true : undefined}
      >
        {viewMode === "illustrated" &&
          board &&
          (screen === "home" && board.illustration ? (
            <LocationArtwork
              board={board}
              onSelect={() =>
                document
                  .getElementById("dala-setup")
                  ?.scrollIntoView({ behavior: "smooth", block: "start" })
              }
            />
          ) : (
            <IllustratedBoard
              board={board}
              match={screen === "room" ? match : null}
              appearances={appearances}
              selected={screen === "room" ? selected : -1}
              onSelect={selectMapTile}
              onAnimate={setAnimating}
              zoom={mapZoom}
              rotation={mapRotation}
            />
          ))}
      </div>
      <div className="dala-wash" />
      <header className="dala-header">
        <button
          className="ui-brand-trigger"
          aria-label="QazaqPlay — басты бет"
          onClick={() => {
            if (!busy) setScreen("home");
          }}
        >
          <Brand subtitle="Дала дәулеті · Үстел ойыны" />
        </button>
        <nav aria-label="Мәзір">
          {!board?.illustration && (
            <button
              className="dala-icon dala-view-toggle"
              aria-label={
                viewMode === "illustrated"
                  ? "Көлемді 3D көрініс"
                  : "Суретті көрініс"
              }
              onClick={() => {
                setViewMode((mode) =>
                  mode === "illustrated" ? "3d" : "illustrated",
                );
                setAnimating(false);
                setMapZoom(1);
                setMapRotation(0);
                setWorldError(false);
              }}
            >
              {" "}
              {viewMode === "illustrated" ? "3D" : "2D"}{" "}
            </button>
          )}
          <button
            className="dala-icon"
            aria-label="Рейтинг"
            onClick={() => setPanel("ranking")}
          >
            <Trophy size={18} />
          </button>
          <button
            className="dala-icon"
            aria-label="Ойын ережелері"
            onClick={() => setPanel("help")}
          >
            <HelpCircle size={20} />
          </button>
          <button className="dala-icon" aria-label="Менің партияларым" onClick={() => setPanel("history")}><History size={18} /></button>
          <button
            className="dala-icon"
            aria-label="Кинотеатр"
            onClick={() => navigateApp("cinema")}
          >
            <Clapperboard size={18} />
          </button>
        </nav>
      </header>
      {error && (
        <div className="dala-message error" role="alert">
          {error}
          <button
            onClick={() =>
              catalog ? void perform(retry.current) : setReload((v) => v + 1)
            }
          >
            Қайталау
          </button>
          <button aria-label="Хабарламаны жабу" onClick={() => setError("")}>
            <X size={15} />
          </button>
        </div>
      )}
      {notice && (
        <div className="dala-message" role="status">
          {notice}
          <button aria-label="Хабарламаны жабу" onClick={() => setNotice("")}>
            <X size={15} />
          </button>
        </div>
      )}
      {!connection && (
        <div className="dala-offline" role="status">
          Байланыс қалпына келуде… Соңғы сақталған партия көрсетілуде.
        </div>
      )}
      {worldError && (
        <div className="dala-webgl">
          <MapPin size={28} />
          <b>3D көрінісін жүктеу мүмкін болмады.</b>
          <small>Суретті көріністі таңдап ойнай беруге болады.</small>
        </div>
      )}
      {!catalog || !board ? (
        <div className="dala-loading" role="status">
          <Dices size={36} />
          <p>Ойын алаңы дайындалуда…</p>
          <button
            className="dala-secondary"
            onClick={() => setReload((v) => v + 1)}
          >
            Қайта ашу
          </button>
        </div>
      ) : screen === "home" ? (
        <HomeScreen
          catalog={catalog}
          board={board}
          scenario={scenario}
          view={view}
          scenarioId={scenarioId}
          name={name}
          busy={busy}
          practice={!!gateway?.practice}
          setName={setName}
          setBoardId={setBoardId}
          setScenarioId={setScenarioId}
          setScreen={setScreen}
          setPanel={setPanel}
          setLearning={setLearning}
          requestCreate={requestCreate}
          appearance={appearance}
          onPortrait={choosePortrait}
        />
      ) : room && !match ? (
        <LobbyScreen
          catalog={catalog}
          board={board}
          scenario={scenario}
          view={view!}
          busy={busy}
          practice={!!gateway?.practice}
          send={send}
          copyInvite={copyInvite}
          copyCode={() => void copyText(view!.code, "Бөлме коды көшірілді.")}
          shareInvite={() => openTelegramLink(shareRoomLink(BOT_URL, view!.code))}
          setVisibility={(value) => void perform(async () => setRoom(await gateway!.setVisibility(view!.code, value)))}
          onLeave={() => setPanel("leave")}
        />
      ) : match && view && scenario ? (
        <>
          <div className="dala-game-top">
            <span>
              <MapPin size={14} />
              {board.name}
            </span>
            <b>
              {match.round} / {scenario.round_limit || "∞"}
              <small> айналым</small>
            </b>
            <span className="dala-mode-badge">
              {gateway?.practice ? "Жаттығу" : `${view.code}`}
              {board.tiles.length !== 40 && <button className="dala-legacy-upgrade" onClick={() => {
                pendingNew.current = catalog!.scenarios.find((s) => s.board === board.id && s.round_limit === 0) ?? catalog!.scenarios[0];
                setPanel("new");
              }}>40 ұяшықты жаңа ойын</button>}
            </span>
          </div>
          <aside className="dala-players" aria-label="Қатысушылар">
            {match.players.map((p, i) => (
              <button
                key={p.id}
                className={`dala-player ${match.turn === i ? "active" : ""} ${p.bankrupt ? "bankrupt" : ""}`}
                onClick={() => {
                  setAssetsPlayer(i);
                  setPanel("assets");
                }}
              >
                <span
                  className="dala-avatar"
                  style={{ "--avatar": p.color } as CSSProperties}
                >
                  <PlayerAvatar appearance={playerAppearance(p, appearances)} color={p.color} size={44} />
                  {i === match.winner && match.phase === "finished" && (
                    <Crown size={14} />
                  )}
                </span>
                <div>
                  <b>
                    {p.name}
                    <small>{i === me ? "Сен" : p.bot ? "Бот" : ""}</small>
                  </b>
                  <strong><CoinAmount value={p.cash} /></strong>
                  <span>Капитал {money(netWorth(board, match, i))}</span>
                </div>
                <i style={{ background: p.color }} />
              </button>
            ))}
          </aside>
          <div className="dala-map-tools">
            <button
              aria-label="Алаңды бұру"
              onClick={() =>
                viewMode === "3d"
                  ? world.current?.rotate()
                  : setMapRotation((value) => value + 5)
              }
            >
              <RotateCcw size={17} />
            </button>
            <button
              aria-label="Жақындату"
              onClick={() =>
                viewMode === "3d"
                  ? world.current?.zoom(0.15)
                  : setMapZoom((value) => Math.min(1.5, value + 0.12))
              }
            >
              <ZoomIn size={18} />
            </button>
            <button
              aria-label="Алыстату"
              onClick={() =>
                viewMode === "3d"
                  ? world.current?.zoom(-0.15)
                  : setMapZoom((value) => Math.max(0.7, value - 0.12))
              }
            >
              <ZoomOut size={18} />
            </button>
            <button aria-label="Сауда және айырбас" onClick={() => setPanel("offers")}><HandCoins size={18} />{inbox.length > 0 && <span className="dala-tool-count">{inbox.length}</span>}</button>
            <button aria-label="Партия шежіресі" onClick={() => setPanel("journal")}><ScrollText size={18} /></button>
            <button
              aria-label="Барлық кәсіптер"
              onClick={() => {
                setAssetsPlayer(-1);
                setPanel("assets");
              }}
            >
              <MapPin size={18} />
            </button>
          </div>
          <aside className="dala-selected-card">
            {selectedTile ? (
              <>
                <span className="dala-eyebrow">ТАҢДАЛҒАН КӘСІП</span>
                <h2>{selectedTile.name}</h2>
                <span
                  className="dala-color-line"
                  style={{ background: selectedTile.color }}
                />
                <div className="dala-selected-owner">
                  <i style={{ background: owner?.color ?? "#aaa98f" }} />
                  {owner?.name ?? "Банк"}
                </div>
                <b className="dala-selected-price">
                  {money(selectedTile.price || selectedTile.amount)}
                </b>
                <button
                  className="dala-secondary dala-full"
                  onClick={() => setPanel("property")}
                >
                  Карточканы ашу <ChevronRight size={15} />
                </button>
              </>
            ) : (
              <>
                <span className="dala-eyebrow">ӨЗ ЖОЛЫҢДЫ ТАҢДА</span>
                <Landmark size={35} />
                <h2>Алаң тірі.</h2>
                <p>Кез келген ұяшықты басып, кәсіпті зертте.</p>
                <button
                  className="dala-secondary"
                  onClick={() => {
                    setAssetsPlayer(-1);
                    setPanel("assets");
                  }}
                >
                  Кәсіптер тізімі
                </button>
              </>
            )}
          </aside>
          <div className="dala-turn-note" aria-live="polite">
            {gameText(match.log.at(-1) ?? "")}
          </div>
          <AssetStrip board={board} match={match} me={me} onSelect={selectMapTile} />
          <section
            className={`dala-turn-dock phase-${match.phase}`}
            aria-label="Жүрісті басқару"
          >
            <div className="dala-turn-person">
              <span
                className="dala-turn-dot"
                style={{ background: match.players[match.turn].color }}
              />
              <div>
                <b>
                  {match.phase === "finished"
                    ? "Партия аяқталды"
                    : myTurn
                      ? "Сенің жүрісің"
                      : `${match.players[match.turn].name} жүрісі`}
                </b>
                <small>
                  {match.classic && String(match.turn) in match.classic.jailed ? "Түрмеде: дубль немесе 50 ◈ төлеп шық." : animating
                    ? "Фишкалар қозғалып жатыр…"
                    : match.phase === "buy"
                      ? board.tiles[match.pending]?.name
                      : match.phase === "debt"
                        ? `Төлем: ${money(match.debt?.amount ?? 0)}`
                        : "Екі кубик. Үлкен мүмкіндіктер."}
                </small>
              </div>
            </div>
            <div className="dala-dice-pair">
              <Dice value={match.dice[0]} rolling={busy || animating} />
              <Dice value={match.dice[1]} rolling={busy || animating} />
            </div>
            <div className="dala-turn-actions">
              {match.phase === "finished" ? (
                <button
                  className="dala-primary"
                  onClick={() => setPanel("result")}
                >
                  Қорытынды <Trophy size={17} />
                </button>
              ) : myTurn ? (
                match.phase === "roll" ? (
                  <>
                  {match.classic && String(me) in match.classic.jailed && <button className="dala-secondary dala-action-sell" disabled={disabled || player!.cash < 50} onClick={() => send("bail")}>Түрмеден шығу · 50 ◈</button>}
                  <button
                    className="dala-primary"
                    disabled={disabled}
                    onClick={() => send("roll")}
                  >
                    <Dices size={20} />
                    {disabled ? "Кубиктер айналуда…" : "Кубик лақтыру"}
                  </button>

                  </>
                ) : match.phase === "buy" ? (
                  <>
                    <button
                      className="dala-primary dala-action-buy"
                      disabled={
                        disabled ||
                        player!.cash < board.tiles[match.pending].price
                      }
                      onClick={() => send("buy")}
                    >
                      <ShoppingBag size={17} /> Сатып алу ·{" "}
                      {money(board.tiles[match.pending].price)}
                    </button>
                    <button
                      className="dala-pass"
                      disabled={disabled}
                      onClick={() => send("pass")}
                    >
                      Өткізу
                    </button>
                  </>
                ) : match.phase === "debt" ? (
                  <>
                    <button
                      className="dala-primary"
                      disabled={
                        disabled || player!.cash < (match.debt?.amount ?? 0)
                      }
                      onClick={() => send("settle")}
                    >
                      <GameCoin size={18} /> Төлеу
                    </button>
                    <button
                      className="dala-secondary"
                      onClick={() => {
                        setAssetsPlayer(me);
                        setPanel("assets");
                      }}
                    >
                      Мүлікті басқару
                    </button>
                  </>
                ) : (
                  <button
                    className="dala-primary"
                    disabled={disabled}
                    onClick={() => send("end")}
                  >
                    Жүрісті аяқтау <ArrowRight size={18} />
                  </button>
                )
              ) : (
                <div className="dala-waiting">
                  <Users size={17} />
                  <span>{match.players[match.turn].bot ? "Боттар ойнап жатыр…" : "Қатысушыны күтеміз…"}</span>
                  {(canTimeout || !!match.players[match.turn].bot) && (
                    <button
                      className="dala-secondary"
                      disabled={disabled}
                      onClick={() => send("timeout")}
                    >
                      {match.players[match.turn].bot ? "Боттар ойынын жалғастыру" : "Уақыты өтті · авто-жүріс"}
                    </button>
                  )}
                </div>
              )}
            </div>
          </section>
        </>
      ) : null}
      {panel && catalog && board && (
        <QuestDialog
          title={
            {
              rooms: "Бөлме табу",
              channel: "Арнаға жазылу",
              create: "Бөлме құру",
              history: "Менің партияларым",
              help: "Ойын ережелері",
              ranking: "Үздік кәсіпкерлер",
              join: "Бөлмеге қосылу",
              property: selectedTile?.name ?? "Кәсіп",
              assets:
                assetsPlayer >= 0
                  ? `${match?.players[assetsPlayer]?.name ?? ""} · мүлік`
                  : "Барлық кәсіптер",
              offers: "Сауда ұсыныстары",
              journal: "Партия шежіресі",
              leave: "Бөлмеден шығу",
              new: "Жаңа партия",
              result: "Дәулет қорытындысы",
              telegram: "Достармен бір үстелде",
            }[panel]
          }
          onClose={close}
        >
          <div className="dala-dialog-content">
            {panel === "channel" && gateway && <GameChannelGate gateway={gateway} onAllowed={() => { setPanel(null); setNotice("Жазылым расталды. Ойынды бастауға болады."); }} />}
            {notice && <p className="dala-inline-notice">{notice}</p>}
            {error && <p className="dala-inline-notice" role="alert">{error}</p>}
            {panel === "rooms" && gateway && <RoomExplorer gateway={gateway} catalog={catalog} busy={busy}
              onJoin={(value) => { setCode(value); join(value); }} onCode={() => setPanel("join")}
              onCreate={() => { setIsPublic(true); setPanel("create"); }} />}
            {panel === "create" && <form className="dala-room-create" onSubmit={(event) => {
              event.preventDefault();
              if (gateway?.practice) openTelegramLink(`${BOT_URL}?startapp=${isPublic ? "quest_create_public" : "quest_create"}`);
              else requestCreate();
            }}>
              <p className="dala-muted">Түрін таңда, бөлмені құр, досыңды шақыр. Екі ойыншыдан бастап ойнайсыңдар.</p>
              <label htmlFor="dala-create-name">Ойындағы атың</label>
              <input id="dala-create-name" value={name} maxLength={24} onChange={(e) => setName(e.target.value)} />
              <label htmlFor="dala-create-scenario">Карта және режим</label>
              <select id="dala-create-scenario" value={scenarioId} onChange={(e) => {
                setScenarioId(e.target.value); setBoardId(catalog.scenarios.find((s) => s.id === e.target.value)!.board);
              }}>{catalog.scenarios.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
              <fieldset className="dala-visibility"><legend>Кім қосыла алады?</legend>
                <label><input type="radio" name="room-visibility" checked={!isPublic} onChange={() => setIsPublic(false)} /><LockKeyhole size={20} /><span><b>Тек достар</b><small>Сілтеме не код арқылы. Жалпы тізімде көрінбейді.</small></span></label>
                <label><input type="radio" name="room-visibility" checked={isPublic} onChange={() => setIsPublic(true)} /><Globe2 size={20} /><span><b>Барлығына ашық</b><small>Басқа ойыншылар бөлмеңді тізімнен таба алады.</small></span></label>
              </fieldset>
              {gateway?.practice && <p className="dala-inline-notice">Ортақ бөлме Telegram ішінде құрылады. Браузердегі жаттығуың сақталады.</p>}
              <button className="dala-primary dala-full" disabled={busy || !name.trim()} type="submit"><Users size={18} />{gateway?.practice ? "Telegram-да бөлме құру" : "Бөлмені құру"}</button>
            </form>}
            {panel === "property" && match && (
              <PropertyPanel
                key={selected}
                board={board}
                match={match}
                me={me}
                selected={selected}
                scenario={scenario}
                disabled={disabled}
                onCommand={send}
              />
            )}
            {panel === "join" && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  join();
                }}
              >
                <p className="dala-muted">
                  Досың жіберген кодты немесе шақыру сілтемесін қой. Ол бірден осы бөлмені ашады.
                </p>
                <label htmlFor="dala-join-name">Ойындағы атың</label>
                <input
                  id="dala-join-name"
                  value={name}
                  maxLength={24}
                  onChange={(e) => setName(e.target.value)}
                />
                <AppearancePicker appearance={appearance} onChange={choosePortrait} />
                <label htmlFor="dala-code">Код немесе шақыру сілтемесі</label>
                <input
                  id="dala-code"
                  value={code}
                  maxLength={2048}
                  placeholder="A1B2C3D4E5 немесе https://t.me/…"
                  autoCapitalize="characters"
                  spellCheck={false}
                  onChange={(e) => setCode(e.target.value)}
                />
                <button
                  type="submit"
                  className="dala-primary dala-full"
                  disabled={
                    busy || !roomCode(code) || !name.trim()
                  }
                >
                  {gateway?.practice ? "Telegram-да бөлмеге кіру" : "Бөлмеге кіру"} <ArrowRight size={17} />
                </button>
              </form>
            )}
            {panel === "telegram" && (
              <div className="dala-empty">
                <Users size={42} />
                <h3>Достарыңды шақыр.</h3>
                <p>
                  Ортақ бөлмелер Telegram арқылы ашылады. Ал осы браузерде
                  боттармен жаттыға аласың.
                </p>
                <button
                  className="dala-primary"
                  onClick={() =>
                    openTelegramLink(
                      `${BOT_URL}?startapp=${code ? `quest_room_${code}` : "quest"}`,
                    )
                  }
                >
                  Telegram-да ашу <ArrowRight size={16} />
                </button>
                <button
                  className="dala-text-button"
                  onClick={() => setPanel(null)}
                >
                  Жаттығуда қалу
                </button>
              </div>
            )}
            {panel === "assets" && match && (
              <>
                <p className="dala-muted">
                  Кәсіпті басып, бағасын, жалдау ақысын және басқару әрекеттерін
                  аш.
                </p>
                <div className="dala-asset-grid">
                  {board.tiles.map((tile, i) => {
                    if (!["property", "station", "utility"].includes(tile.kind))
                      return null;
                    const lot = match.lots[i];
                    if (assetsPlayer >= 0 && lot?.owner !== assetsPlayer)
                      return null;
                    return (
                      <button
                        key={tile.id}
                        style={{ "--deed-color": tile.color } as CSSProperties}
                        onClick={() => {
                          setSelected(i);
                          setPanel("property");
                        }}
                      >
                        <span />
                        <b>{tile.name}</b>
                        <small>
                          {lot ? match.players[lot.owner].name : "Банк"}
                          {lot?.mortgaged ? " · кепілде" : ""}
                        </small>
                        <strong>
                          {lot
                            ? `${lot.level === tile.rents.length - 1 ? "Қонақүй" : `${lot.level} ғимарат`} · ${money(rentFor(board, match, i))}`
                            : money(tile.price)}
                        </strong>
                      </button>
                    );
                  })}
                </div>
                {assetsPlayer >= 0 &&
                  !Object.values(match.lots).some(
                    (lot) => lot.owner === assetsPlayer,
                  ) && (
                    <p className="dala-empty">
                      Әзірге сатып алынған кәсіп жоқ.
                    </p>
                  )}
                {match.phase === "debt" && myTurn && (
                  <div className="dala-debt-summary">
                    <p>
                      Төлем үшін ғимарат сатуға немесе кәсіпті кепілге қоюға
                      болады.
                    </p>
                    <button
                      className="dala-secondary"
                      disabled={busy}
                      onClick={() => send("bankrupt")}
                    >
                      Төлей алмаймын · банкрот болу
                    </button>
                  </div>
                )}
              </>
            )}
            {panel === "offers" && match && <TradeOffers board={board} match={match} me={me}
              disabled={disabled} send={send} />}
            {panel === "journal" && match && (
              <ol className="dala-journal">
                {match.log.map((line, i) => (
                  <li key={i}>{gameText(line)}</li>
                ))}
              </ol>
            )}
            {panel === "leave" && view && (
              <>
                <p>Бөлмеден шығасың. Қалған қатысушылар ойынды бастай алады.</p>
                <button
                  className="dala-primary dala-full"
                  disabled={busy}
                  onClick={() =>
                    void perform(async () => {
                      await gateway!.leave(view.code);
                      latest.current = null;
                      setView(null);
                      setScreen("home");
                      setPanel(null);
                      try {
                        localStorage.removeItem(LIVE_ROOM_KEY);
                      } catch {
                        /* Қайта кіруге кедергі емес. */
                      }
                    })
                  }
                >
                  Бөлмеден шығу
                </button>
              </>
            )}
            {panel === "new" && (
              <>
                <p><b>{pendingNew.current?.name}</b></p>
                {match && match.catalog_version < catalog.version && <p className="dala-inline-notice">Қазіргі партия — бұрынғы 24 ұяшықты нұсқа. Жаңа партия классикалық 40 ұяшықпен басталады.</p>}
                <p>
                  Жаңа бөлме ашылады.{" "}
                  {gateway?.practice
                    ? "Осы браузердегі жаттығу жаңадан басталады."
                    : "Басталған ортақ партияда өз жүрісіңе жауапты болып қаласың."}
                </p>
                <button
                  className="dala-primary dala-full"
                  disabled={busy}
                  onClick={() =>
                    pendingNew.current && create(pendingNew.current)
                  }
                >
                  Жаңа партияны ашу
                </button>
                <button className="dala-text-button" onClick={close}>
                  Қазіргі партияға оралу
                </button>
              </>
            )}
            {panel === "result" && match && (
              <div className="dala-result">
                <span>
                  <Trophy size={48} />
                </span>
                <span className="dala-eyebrow">ПАРТИЯНЫҢ ЖЕҢІМПАЗЫ</span>
                <h3>
                  {match.players[match.winner]?.name ?? "Партия аяқталды"}
                </h3>
                <p>
                  Қорытынды капитал:{" "}
                  {money(
                    match.winner >= 0
                      ? netWorth(board, match, match.winner)
                      : 0,
                  )}
                </p>
                <ol>
                  {match.players
                    .map((p, i) => ({ p, i, value: netWorth(board, match, i) }))
                    .sort((a, b) => b.value - a.value || a.i - b.i)
                    .map(({ p, i, value }, rank) => (
                      <li key={p.id}>
                        <b>{rank + 1}</b>
                        <i style={{ background: p.color }} />
                        <span>
                          {p.name}
                          {i === me ? " · Сен" : ""}
                        </span>
                        <strong>{money(value)}</strong>
                      </li>
                    ))}
                </ol>
                <small>
                  {gateway?.practice
                    ? "Жаттығу нәтижелері рейтингке кірмейді."
                    : "Сценарийдегі алғашқы жеңіске ғана рейтингілік ұпай беріледі."}
                </small>
                <button
                  className="dala-primary dala-full"
                  onClick={() => {
                    setPanel(null);
                    setScreen("home");
                  }}
                >
                  Жаңа партия таңдау <ArrowRight size={17} />
                </button>
              </div>
            )}
            {(panel === "ranking" || panel === "history") && gateway && <GameRecords key={panel} gateway={gateway} catalog={catalog} mode={panel} />}
            {panel === "help" && (
              <div className="dala-help">
                <p>
                  Мақсат — партия соңында ең көп капитал жинау. Капиталға
                  қолма-қол ақша, кәсіптер мен салынған ғимараттар кіреді; кепіл
                  қарызы шегеріледі.
                </p>
                <ol>
                  <li>
                    <b>Жүріс.</b> Екі кубик лақтырып, фишканы жылжыт. {board.tiles.length === 40 ? "Дубль тағы бір лақтыру береді. Қатарынан үш дубль — түрме." : "Бұл бұрынғы партияда дубль қосымша жүріс бермейді."} Бастаудан өткенде айналым табысын аласың.
                  </li>
                  <li>
                    <b>Кәсіп.</b> Бос кәсіпті сатып ал немесе өткіз. Өзге
                    ойыншының кәсібіне түссең, жалдау ақысын төлейсің.
                    Өткізілген кәсіп банкте қалады.
                  </li>
                  <li>
                    <b>Түсті топ.</b> Бір түстегі кәсіптерді толық жинасаң,
                    бастапқы жалдау ақысы екі еселенеді. Ғимараттарды топ ішінде
                    біркелкі сал. {board.tiles.length === 40 ? "Төрт үйден кейін қонақүй салынады." : "Төртінші жақсарту — қонақүй."}
                  </li>
                  <li>
                    <b>Қаражат.</b> Ғимаратты жарты бағасына сатуға, бос кәсіпті
                    жарты бағасына кепілге қоюға болады. Кепілден қайтару —
                    қарыз және 10% үстеме.
                  </li>
                  <li>
                    <b>Сауда.</b> Кәсіпті сатып алуды не сатуды ұсын, кәсіпке кәсіп айырбаста. Қарсы баға ұсынып саудалас. Мәміле екінші тарап келіскенде ғана орындалады.
                  </li>
                  <li>
                    <b>Арнайы ұяшықтар.</b> {board.tiles.length === 40 ? "Төрт вокзал: жалдау 25 / 50 / 100 / 200 ◈. Екі коммуналдық қызмет: кубик × 4 немесе × 10. Түрмеден дубльмен не 50 ◈ төлеп шық; үшінші сәтсіз лақтыруда 50 ◈ міндетті. Тегін тұрақта төлем жоқ." : "Бұл бұрынғы партияда көлік пен демалыс ұяшықтары бар."} Сәттілік карталары кездейсоқ оқиға береді.
                  </li>
                  <li>
                    <b>Достар.</b> Бөлме иесі бот қосады және партияны бастайды.
                    Адамдар дайын екенін растайды. Жүріске 3 минут беріледі;
                    уақыт өтсе, бөлмедегі қатысушы авто-жүрісті іске қоса алады.
                  </li>
                  <li>
                    <b>Қорытынды.</b> {scenario?.round_limit === 0 ? "Айналым шектелмейді. Басқалар банкрот болғанда, соңғы қалған ойыншы жеңеді." : "Айналым лимиті біткенде немесе бір ойыншы қалған кезде капитал салыстырылады. Тең капиталда үстелдегі бастапқы орын реті қолданылады."}
                  </li>
                </ol>
                <p>
                  {gateway?.practice
                    ? "Бұл партия құрылғыңда есептеліп, осы браузерде сақталады."
                    : "Графика құрылғыңда жұмыс істейді. Ортақ жүрістер мен кубик нәтижесін сервер тексереді."}
                </p>
              </div>
            )}
          </div>
        </QuestDialog>
      )}
    </main>
  );
}
