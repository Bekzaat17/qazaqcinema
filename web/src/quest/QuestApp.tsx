import { YurtIcon, WellIcon } from "../ui-kit/GameIcons";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Clapperboard,
  Hammer,
  ArrowRight,
  Check,
  Compass,
  Dices,
  Gem,
  HelpCircle,
  Leaf,
  Mountain,
  Settings2,
  Sparkles,
  TreePine,
  Trophy,
  WandSparkles,
} from "../ui-kit/adapters/icons";
import { ApiError, NetworkError, SessionExpiredError } from "../lib/api";
import {
  BOT_URL,
  getInitData,
  getWebApp,
  haptic,
  openTelegramLink,
  showBackButton,
} from "../lib/telegram";
import { Brand, Progress as ProgressBar } from "../ui-kit";
import QuestDialog from "./components/QuestDialog";
import ResourceJournal from "./components/ResourceJournal";
import { buildingShortfall, dailyTasks } from "./resources";
import Joystick from "./components/Joystick";
import RankingPanel from "./components/RankingPanel";
import { HttpQuestGateway } from "./gateway";
import { PracticeQuestGateway } from "./practice";
import { navigateApp } from "./launch";
import {
  PLOTS,
  SHRINES,
  type Building,
  type Progress,
  type Quality,
  type QuestId,
  type Run,
  type WorldTarget,
} from "./types";
import { QuestEngine } from "./world/engine";
import "./quest.css";

type Panel = "village" | "ranking" | "help" | "lesson" | "resources" | "guide" | null;

function errorText(error: unknown): string {
  if (error instanceof SessionExpiredError)
    return "Сессия аяқталды. Ойынды Telegram-нан қайта аш.";
  if (error instanceof NetworkError)
    return "Байланыс үзілді. Жауабыңды қайта жіберуге болады — ұпай екі рет есептелмейді.";
  if (error instanceof ApiError)
    return (
      (
        {
          quest_locked: "Алдымен алдыңғы рухты оят.",
          quest_run_expired: "Жаңа күн басталды. Сынақты жауып, қайта аш.",
          quest_not_enough_materials:
            "Материал жеткіліксіз. Рухтардың тапсырмаларын орында.",
          too_many_requests: "Бір сәт күте тұр да, қайта көр.",
          quest_unavailable:
            "Ауылды сақтау қызметі уақытша қолжетімсіз. Қайталап көр.",
        } as Record<string, string>
      )[error.code] ?? "Әрекет орындалмады. Қайталап көр."
    );
  return error instanceof Error ? error.message : "Қате шықты. Қайталап көр.";
}

export default function QuestApp({ onReturn }: { onReturn?: () => void }) {
  const [gateway] = useState(() =>
    getInitData() ? new HttpQuestGateway() : new PracticeQuestGateway(),
  );
  const host = useRef<HTMLDivElement>(null);
  const engine = useRef<QuestEngine | null>(null);
  const action = useRef<() => void>(() => {});
  const inFlight = useRef(false);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [playing, setPlaying] = useState(false);
  const [near, setNear] = useState<WorldTarget | null>(null);
  const [panel, setPanel] = useState<Panel>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [lessonTitle, setLessonTitle] = useState("");
  const [rewardReceived, setRewardReceived] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [worldError, setWorldError] = useState(false);
  const [quality, setQuality] = useState<Quality>(() =>
    window.innerWidth < 800 ? "low" : "high",
  );
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const originalTitle = document.title;
    document.title = "QazaqPlay — Менің ауылым";
    if (getInitData()) {
      getWebApp()?.setHeaderColor("#d5e4dc");
      getWebApp()?.setBackgroundColor("#d5e4dc");
    }
    try {
      engine.current = new QuestEngine(
        host.current!,
        {
          near: setNear,
          interact: () => action.current(),
          error: () => setWorldError(true),
        },
        quality,
      );
    } catch {
      setWorldError(true);
    }
    return () => {
      engine.current?.dispose();
      engine.current = null;
      document.title = originalTitle;
      if (getInitData()) {
        getWebApp()?.setHeaderColor("#09090b");
        getWebApp()?.setBackgroundColor("#09090b");
      }
    };
    // Качество меняется отдельным методом, без пересоздания WebGL-контекста.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let active = true;
    setError("");
    gateway
      .progress()
      .then((value) => {
        if (active) setProgress(value);
      })
      .catch((e) => {
        if (active) setError(errorText(e));
      });
    return () => {
      active = false;
    };
  }, [gateway, reload]);
  useEffect(() => {
    const calendar = new Intl.DateTimeFormat("sv-SE", {
      timeZone: "Asia/Almaty",
    });
    let day = calendar.format(new Date());
    let active = true;
    const refreshDay = () => {
      const current = calendar.format(new Date());
      if (document.hidden || inFlight.current || current === day) return;
      day = current;
      gateway
        .progress()
        .then((value) => {
          if (active) setProgress(value);
        })
        .catch(() => {
          day = "";
        });
    };
    // Локальные часы, не опрос API: запрос только при смене календарного дня.
    const timer = window.setInterval(refreshDay, 60_000);
    document.addEventListener("visibilitychange", refreshDay);
    return () => {
      active = false;
      clearInterval(timer);
      document.removeEventListener("visibilitychange", refreshDay);
    };
  }, [gateway]);
  useEffect(() => {
    engine.current?.setQuality(quality);
  }, [quality]);
  useEffect(() => {
    engine.current?.setPlaying(playing);
  }, [playing]);
  useEffect(() => {
    engine.current?.setPaused(panel !== null || worldError);
  }, [panel, worldError]);
  useEffect(() => {
    if (progress) engine.current?.setProgress(progress);
  }, [progress]);
  useEffect(() => {
    if (!getInitData()) return;
    return showBackButton(() => {
      if (inFlight.current) return;
      if (panel) setPanel(null);
      else if (playing) setPlaying(false);
      else if (onReturn) onReturn();
      else navigateApp("cinema");
    });
  }, [panel, playing, onReturn]);

  const perform = useCallback(async (operation: () => Promise<void>) => {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    try {
      await operation();
    } catch (e) {
      setError(errorText(e));
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }, []);

  const startQuest = (target: WorldTarget) => {
    if (inFlight.current) return;
    setLessonTitle(target.name);
    setRewardReceived(false);
    setPanel("lesson");
    setRun(null);
    setFeedback("");
    void perform(async () => {
      setRun(await gateway.start(target.id as QuestId));
    });
  };
  const interact = () => {
    if (busy || panel || !playing) return;
    haptic.light();
    engine.current?.cast();
    if (near?.kind === "quest") startQuest(near);
    else if (near?.kind === "building") setPanel("village");
    else setFeedback("Рухқа жақында немесе картадан бағыт таңда.");
  };
  action.current = interact;
  const chooseAnswer = (answer: string) => {
    if (!run) return;
    void perform(async () => {
      const result = await gateway.answer(run, answer);
      setRun(result.run);
      setProgress(result.progress);
      setFeedback(
        result.outcome === "wrong"
          ? "Қайта ойланып көр. Келесі дұрыс жауапқа 10 ұпай беріледі."
          : (result.explanation ?? "Сақталған нәтиже қалпына келтірілді."),
      );
      if (result.outcome === "correct") {
        haptic.success();
        if (result.run.complete) {
          setRewardReceived(true);
          engine.current?.cast();
        }
      }
    });
  };
  const build = (building: Building) =>
    void perform(async () => {
      setProgress(await gateway.build(building));
      setFeedback(`${building.name} — ${building.level ? "жақсартылды" : "салынды"}!`);
      haptic.success();
    });
  const closePanel = () => {
    if (!busy) {
      setPanel(null);
      setError("");
      setFeedback("");
    }
  };
  const openPanel = (next: Panel) => {
    setError("");
    setFeedback("");
    setPanel(next);
  };
  const tasks = progress ? dailyTasks(progress, SHRINES) : [];
  const nextQuest = tasks.find((task) => !task.done && !task.locked)?.target;
  const firstBuild = progress?.buildings.every((building) => building.level === 0) ?? true;
  const guiding = firstBuild;
  const villageLevel =
    progress?.buildings.reduce((sum, building) => sum + building.level, 0) ?? 0;
  useEffect(() => {
    if (panel !== "village" || !guiding || !progress?.total_xp) return;
    const frame = requestAnimationFrame(() => {
      document.querySelector(".quest-build-highlight")?.scrollIntoView({ block: "center" });
    });
    return () => cancelAnimationFrame(frame);
  }, [panel, guiding, progress?.total_xp]);


  return (
    <main className={`quest-app ${playing ? "is-playing" : "is-intro"}`}>
      <div className="quest-world" ref={host} />
      {!playing && <div className="quest-world-wash" />}
      <header className="quest-header">
        <a
          className="ui-brand-trigger"
          href="/quest"
          aria-label="QazaqPlay — Менің ауылым"
          onClick={(event) => {
            event.preventDefault();
            setPanel(null);
            setPlaying(false);
          }}
        >
          <Brand subtitle="Менің ауылым · Сиқырлы алқап" />
        </a>
        <nav aria-label="Ойын мәзірі">
          {onReturn && (
            <button className="quest-nav quest-board-return" disabled={busy} onClick={onReturn}>
              <Dices size={18} /><span>Дала дәулеті</span>
            </button>
          )}
          <button
            className="quest-nav"
            aria-label="Рейтинг"
            onClick={() => openPanel("ranking")}
          >
            <Trophy size={18} />
            <span>Рейтинг</span>
          </button>
          <button
            className="quest-icon"
            aria-label="Ойын ережелері"
            onClick={() => openPanel("help")}
          >
            <HelpCircle size={20} />
          </button>
          <a
            className="quest-cinema"
            aria-label="Кинотеатр"
            href="/"
            onClick={(event) => {
              event.preventDefault();
              navigateApp("cinema");
            }}
          >
            <Clapperboard size={15} />
            <span>Кинотеатр</span>
          </a>
        </nav>
      </header>

      {worldError ? (
        <section className="quest-webgl-error">
          <Mountain size={44} />
          <h1>3D әлемі ашылмады</h1>
          <p>
            Бұл браузерде WebGL қолжетімсіз немесе графикалық байланыс үзілді.
            Бетті қайта ашып көр.
          </p>
          <button
            className="quest-primary"
            onClick={() => window.location.reload()}
          >
            Қайта ашу
          </button>
          {onReturn && (
            <button className="quest-secondary" onClick={onReturn}>
              <Dices size={18} /> Үстел ойынына оралу
            </button>
          )}
          <a
            href="/"
            onClick={(event) => {
              event.preventDefault();
              navigateApp("cinema");
            }}
          >
            Кинотеатрға оралу
          </a>
        </section>
      ) : !playing ? (
        <>
          <section className="quest-intro">
            <div className="quest-kicker">
              <span /> ҚАЗАҚША ШЫТЫРМАН · 3D
            </div>
            <h1>
              Өз ауылың.
              <br />
              Өз <em>хикаяң.</em>
            </h1>
            <p className="quest-lead">
              Тылсым орманды зертте. Рухтарды оят.
              <br />
              Үш сұраққа жауап бер → ағаш пен тас ал → ауыл сал.
            </p>
            <div className="quest-intro-actions">
              <button
                className="quest-primary quest-play"
                disabled={!progress || busy}
                onClick={() => {
                  setPlaying(true);
                  if (progress?.total_xp === 0) setPanel("guide");
                  setError("");
                  haptic.medium();
                }}
              >
                <Compass size={21} />
                {progress && progress.total_xp > 0
                  ? "Саяхатты жалғастыру"
                  : "Саяхатты бастау"}
                <ArrowRight size={20} />
              </button>
              <span className="quest-entry-note">
                {gateway.practice
                  ? "Қонақ режимі · орнатусыз"
                  : "Telegram арқылы сақталады"}
              </span>
            </div>
            {!progress && !error && (
              <p role="status" className="quest-muted">
                Ауылың дайындалып жатыр…
              </p>
            )}
            {error && (
              <div className="quest-error" role="alert">
                {error}
                <button onClick={() => setReload((v) => v + 1)}>
                  Қайталау
                </button>
              </div>
            )}
            <button className="quest-intro-guide" disabled={!progress || busy} onClick={() => openPanel("resources")}>
              <TreePine size={18} /><span>Ағаш пен тасты қалай жинаймын?<small lang="ru">Как получить ресурсы для аула</small></span><ArrowRight size={18} />
            </button>
            <div className="quest-intro-stats">
              <span>
                <YurtIcon size={20} />
                <b>Өз ауылың</b>
                <small>Сал және дамыт</small>
              </span>
              <span>
                <Leaf size={20} />
                <b>3 рух</b>
                <small>Тап және оят</small>
              </span>
              <span>
                <Trophy size={20} />
                <b>Апта үздігі</b>
                <small>Біліміңмен жарыс</small>
              </span>
            </div>
          </section>
          <div className="quest-world-label">
            <span className="quest-pulse-dot" /> I ТАРАУ <b>Сиқырлы алқап</b>
            <small>Әр үлкен хикая бір қадамнан басталады</small>
          </div>
          <footer className="quest-intro-footer">
            <span>QazaqCinema әлемінен</span>
            <span>Зертте. Үйрен. Құр.</span>
            <span>01 / Сиқырлы алқап</span>
          </footer>
        </>
      ) : (
        progress && (
          <>
            <div className="quest-hud">
              <div className="quest-level">
                <span>{progress.level}</span>
                <div>
                  <b>Саяхатшы</b>
                  <small>
                    {progress.total_xp} XP ·{" "}
                    {gateway.practice ? "Жаттығу" : "Сақталған"}
                  </small>
                  <div className="quest-xp">
                    <i style={{ width: `${(progress.total_xp % 300) / 3}%` }} />
                  </div>
                </div>
              </div>
              <button className="quest-wallet" onClick={() => openPanel("resources")} aria-label={`Ресурстар: ${progress.wood} ағаш, ${progress.stone} тас. Қалай жинауға болады`}>
                <span><TreePine size={18} /><b>{progress.wood}</b><small>Ағаш</small></span>
                <span><Mountain size={18} /><b>{progress.stone}</b><small>Тас</small></span>
              </button>
              <button className="quest-earn-button" onClick={() => openPanel("resources")}><Sparkles size={16} /> Ресурс жинау <ArrowRight size={15} /></button>
            </div>
            <button className="quest-next-action" disabled={busy} onClick={() => {
              if (guiding && progress.total_xp > 0) openPanel("village");
              else openPanel("resources");
            }}>
              <span className="quest-next-icon">{guiding && progress.total_xp > 0 ? <Hammer size={23} /> : <Leaf size={23} />}</span>
              <span><small>{guiding ? "АЛҒАШҚЫ ҚАДАМДАР · ПЕРВЫЕ ШАГИ" : "ТАПСЫРМАЛАР · ЗАДАНИЯ"}</small><b>{guiding && progress.total_xp > 0 ? "Ресурсы собраны — построй юрту" : nextQuest ? "Получи дерево и камень" : "Все награды дня получены"}</b><span>{guiding && progress.total_xp > 0 ? "25 дерева + 10 камня → первая постройка" : nextQuest ? "Открыть задания · 3 вопроса за награду" : "Новые задания в 00:00 · Алматы"}</span></span><ArrowRight size={20} />
            </button>
            <aside className="quest-missions">
              <div className="quest-card-label"><Compass size={15} /> БҮГІНГІ САЯХАТ <span>{progress.completed_today.length}/3</span></div>
              <p className="quest-mission-intro">3 сұрақ → +25 ағаш, +15 тас</p>
              {tasks.map(({ target, done, locked }) => (
                <button key={target.id} className={`quest-mission ${done ? "is-done" : ""}`} disabled={busy || done || locked} onClick={() => startQuest(target)}>
                  <span className="quest-spirit-dot" style={{ background: target.color }}>{done ? <Check size={14} /> : <Leaf size={14} />}</span>
                  <span><b>{target.name}</b><small>{done ? "Марапат алынды ✓" : locked ? "Алдыңғы рухты оят" : "Тапсырманы бастау →"}</small></span>
                </button>
              ))}
              {!nextQuest && <p className="quest-all-done">Марапаттар алынды! Жаңа тапсырмалар — 00:00, Алматы.</p>}
            </aside>
            {gateway.practice && (
              <div className="quest-practice-note">
                Жаттығу · рейтингке кірмейді{" "}
                <button
                  onClick={() => openTelegramLink(`${BOT_URL}?startapp=quest`)}
                >
                  Telegram-да ойнау ↗
                </button>
              </div>
            )}
            <div className="quest-bottom">
              <div className="quest-movement">
                <Joystick
                  onMove={(x, y) => engine.current?.setJoystick(x, y)}
                />
                <span>WASD / жерді бас</span>
              </div>
              <button
                className="quest-village-button"
                onClick={() => openPanel("village")}
              >
                <YurtIcon size={22} />
                <span>
                  Менің ауылым<small>{villageLevel} / 9 даму</small>
                </span>
              </button>
              <div className="quest-action-wrap">
                <span>{near?.name ?? "Сиқырлы посох"}</span>
                <button
                  className="quest-cast"
                  aria-label={
                    near?.kind === "quest"
                      ? `${near.name} — сынақты бастау`
                      : "Сиқыр қолдану"
                  }
                  onClick={interact}
                >
                  {near?.kind === "building" ? <Hammer size={30} /> : near?.kind === "quest" ? <Leaf size={30} /> : <WandSparkles size={30} />}
                </button>
                <small>
                  {near?.kind === "quest"
                    ? "Рухты оят · E"
                    : near?.kind === "building"
                      ? "Ауылды аш · E"
                      : "Сиқыр · E"}
                </small>
              </div>
            </div>
            {feedback && !panel && (
              <div className="quest-toast" role="status">
                {feedback}
                <button
                  aria-label="Хабарламаны жабу"
                  onClick={() => setFeedback("")}
                >
                  ×
                </button>
              </div>
            )}
          </>
        )
      )}

      {panel && (
        <QuestDialog
          key={panel}
          title={
            {
              village: "Менің ауылым",
              resources: "Ағаш пен тас жинау",
              guide: "Алғашқы қадам · Начнём вместе",
              ranking: "Үздік саяхатшылар",
              help: "Алғашқы қадамың",
              lesson: run?.complete
                ? "Рух оянды!"
                : (lessonTitle || "Рухтың сынағы"),
            }[panel]
          }
          onClose={closePanel}
        >
          {guiding && (panel === "lesson" || panel === "village") && <div className="quest-tour-progress" aria-label="Алғашқы қадамдар">
            <span className={panel === "lesson" && !run?.complete ? "is-current" : ""}>1. Тапсырма</span><ArrowRight size={12} /><span className={progress?.total_xp ? "is-current" : ""}>2. Марапат</span><ArrowRight size={12} /><span className={panel === "village" ? "is-current" : ""}>3. Киіз үй</span>
          </div>}
          {panel === "guide" && progress && <div className="quest-first-steps">
            <div className="quest-guide-art"><YurtIcon size={64} /><span><TreePine size={24} /></span><span><Mountain size={23} /></span></div>
            <h3>Бірге алғашқы үйді салайық</h3>
            <p lang="ru">Давай построим твою первую юрту. Я покажу каждый шаг — искать задания по карте не нужно.</p>
            <ol lang="ru">
              <li><span>1</span><div><b>Ответь на 3 вопроса</b><small>Кнопка ниже сразу откроет задание духа леса. Если ошибёшься, можно ответить ещё раз.</small></div></li>
              <li><span>2</span><div><b>Получи 25 дерева и 15 камня</b><small>Они появятся в запасах после последнего ответа. XP — это опыт, а не монеты.</small></div></li>
              <li><span>3</span><div><b>Построй юрту</b><small>Первая юрта стоит 25 дерева и 10 камня. Одного задания хватит!</small></div></li>
            </ol>
            <button className="quest-primary" disabled={busy} onClick={() => startQuest(tasks[0].target)}>Первое задание <ArrowRight size={19} /></button>
            <button className="quest-text-button" onClick={closePanel}>Сначала осмотрюсь</button>
          </div>}
          {panel === "resources" && progress && <ResourceJournal progress={progress} busy={busy} onStart={startQuest} />}
          {panel === "ranking" && <RankingPanel gateway={gateway} />}
          {panel === "help" && (
            <div className="quest-help">
              <p>
                Сен — осы алқаптың жаңа сақшысысың. Үш рухқа көмектесіп, өз
                ауылыңды тұрғыз.
              </p>
              <ol>
                <li>
                  <b>Зертте.</b> Жерді бас, джойстикті жылжыт немесе WASD
                  қолдан. Картада рухқа қарай жүр немесе тапсырманы бірден аш.
                </li>
                <li>
                  <b>Үйрен.</b> «Ресурс жинау» батырмасын басып, тапсырманы таңда.
                  Немесе рухқа жақындап, E бас. Үш сұраққа жауап бер.
                </li>
                <li>
                  <b>Құр.</b> Әр сынақ 25 ағаш пен 15 тас береді. «Менің ауылым»
                  бөлімінен ғимарат сал.
                </li>
              </ol>
              <p>
                Бірден дұрыс жауап — 30 ұпай, қателескеннен кейін — 10. Үш
                сұрақты аяқтау — тағы 10. Әр рух күніне бір рет марапат береді:
                барлығы 300 ұпайға дейін.
              </p>
              <p>
                Күн мен апта Алматы уақытымен ауысады. Telegram режиміндегі
                жауаптар мен құрылысқа интернет керек. Жаттығудағы аул осы
                браузерде сақталады және рейтингке көшірілмейді.
              </p>
              <button className="quest-primary" disabled={!progress} onClick={() => openPanel("resources")}><TreePine size={18} /> Ресурс жинау</button>
              <div className="quest-quality">
                <Settings2 size={19} />
                <span>Графика</span>
                <button
                  aria-pressed={quality === "low"}
                  onClick={() => setQuality("low")}
                >
                  Үнемді
                </button>
                <button
                  aria-pressed={quality === "high"}
                  onClick={() => setQuality("high")}
                >
                  Әдемі
                </button>
              </div>
            </div>
          )}
          {panel === "village" && progress && (
            <>
              <div className="quest-village-banner"><YurtIcon size={42} /><div><b>Кішкентай ауыл. Үлкен арман.</b><p>Тапсырма орында → материал жина → құрылыс сал</p></div></div>
              <div className="quest-village-progress">
                <span><YurtIcon size={18} /> Ауылдың дамуы <b>{villageLevel} / 9</b></span>
                <ProgressBar value={villageLevel} max={9} label="Ауылдың дамуы" />
                <small>Әр жақсартумен ауылыңда жаңа бөлшектер пайда болады.</small>
              </div>
              <div className="quest-materials">
                <span>
                  <TreePine size={18} /> {progress.wood} ағаш
                </span>
                <span>
                  <Mountain size={18} /> {progress.stone} тас
                </span>
              </div>
              <button className="quest-resource-cta" onClick={() => openPanel("resources")}><span className="quest-resource-cta-icon"><TreePine size={24} /></span><span><b>Ресурс жинау</b><small lang="ru">3 вопроса = 25 дерева + 15 камня</small></span><ArrowRight size={20} /></button>
              {feedback && <p className="quest-feedback" role="status">{feedback}</p>}
              <div className="quest-buildings">
                {progress.buildings.map((building, index) => {
                  const BuildingIcon = { yurt: YurtIcon, well: WellIcon, workshop: Hammer }[building.id];
                  const max = building.wood_cost === null;
                  const missing = buildingShortfall(building, progress);
                  const affordable =
                    !max &&
                    progress.wood >= building.wood_cost! &&
                    progress.stone >= building.stone_cost!;
                  return (
                    <article key={building.id} className={guiding && building.id === "yurt" && affordable ? "quest-build-highlight" : ""}>
                      <div
                        className={`quest-building-art building-${building.id}`}
                      >
                        <BuildingIcon size={36 + index * 2} strokeWidth={1.4} />
                        <span>{building.level || "+"}</span>
                      </div>
                      <div>
                        <h3>{building.name}</h3>
                        {guiding && building.id === "yurt" && affordable && <p className="quest-build-guide" lang="ru">Твоя первая постройка! Нажми «Салу» ↓</p>}
                        <div className="quest-building-levels">
                          {[1, 2, 3].map((level) => (
                            <i
                              key={level}
                              className={
                                level <= building.level ? "filled" : ""
                              }
                            />
                          ))}
                          <small>{building.level}/3</small>
                        </div>
                        <p>
                          {
                            [
                              "Саяхатың басталатын жылы мекен.",
                              "Ауылдың тіршілік көзі.",
                              "Шеберлік пен жаңа идеялар мекені.",
                            ][index]
                          }
                        </p>
                        <button
                          className="quest-secondary"
                          disabled={busy || max || !affordable}
                          onClick={() => build(building)}
                        >
                          {max ? (
                            "Толық дамыған ✓"
                          ) : (
                            <>
                              {building.level ? "Жақсарту" : "Салу"} ·{" "}
                              {building.wood_cost} ағаш / {building.stone_cost}{" "}
                              тас
                            </>
                          )}
                        </button>
                        {!max && !affordable && (
                          <div className="quest-cost-note">
                            <span lang="ru">Не хватает: {[missing.wood ? `${missing.wood} дерева` : "", missing.stone ? `${missing.stone} камня` : ""].filter(Boolean).join(" и ")}.</span>
                            <button onClick={() => openPanel("resources")}>Ресурс жинау <ArrowRight size={14} /></button>
                            <small lang="ru">{missing.lessons} заданий до постройки{missing.lessons > tasks.filter((task) => !task.done).length ? " · понадобятся награды следующих дней" : ""}</small>
                          </div>
                        )}
                      </div>
                    </article>
                  );
                })}
              </div>
              {villageLevel === 9 && (
                <div className="quest-feedback">
                  Ауылың гүлденді! Сен — алқаптың шебер сақшысысың.
                </div>
              )}
              <button
                className="quest-text-button"
                onClick={() => {
                  engine.current?.home();
                  closePanel();
                  setPlaying(true);
                }}
              >
                Ауылға оралу <ArrowRight size={16} />
              </button>
            </>
          )}
          {panel === "lesson" &&
            (!run ? (
              <div className="quest-empty">
                <Sparkles size={36} />
                <p>
                  {busy
                    ? "Рухтың сынағы жүктелуде…"
                    : "Сынақты қайта ашып көр."}
                </p>
              </div>
            ) : run.complete ? (
              <div className="quest-complete">
                <div className="quest-reward-icon">
                  <Gem size={43} />
                </div>
                <h3>{rewardReceived ? "Марапат сенің қоржыныңда!" : "Бүгінгі марапат алынды"}</h3>
                <p>
                  {feedback ||
                    "Бүгінгі сынақ аяқталған. Келесі марапат ертең қолжетімді."}
                </p>
                <div className="quest-reward">
                  <span>
                    <b>{run.points}</b> ұпай
                  </span>
                  <span>
                    <b>25</b> ағаш
                  </span>
                  <span>
                    <b>15</b> тас
                  </span>
                </div>
                <p className="quest-muted">
                  Ағаш пен тас автоматты түрде қосылды. Қайта ашқанда марапат қайталанбайды.
                  {gateway.practice
                    ? " Бұл — жаттығу нәтижесі."
                    : " Прогресс сақталды."}
                </p>
                {guiding && <p className="quest-first-build-hint" lang="ru">Отлично! Этого хватит на первую юрту: 25 дерева и 10 камня. Нажми ниже — покажу, где её построить.</p>}
                <button
                  className="quest-primary"
                  onClick={() => {
                    setPanel("village");
                    setFeedback("");
                  }}
                >
                  {guiding ? "Построить первую юрту" : "Ауылымды дамыту"} <YurtIcon size={20} />
                </button>
                <button className="quest-text-button" onClick={closePanel}>
                  Саяхатты жалғастыру <ArrowRight size={16} />
                </button>
              </div>
            ) : (
              <div className="quest-lesson">
                <div className="quest-lesson-meta">
                  <span>
                    СҰРАҚ {run.question_index + 1} / {run.total_questions}
                  </span>
                  <span>{run.points} ұпай</span>
                </div>
                <div className="quest-lesson-reward"><TreePine size={16} /> +25 ағаш <Mountain size={16} /> +15 тас <span>3 жауаптан кейін</span></div>
                <div className="quest-question-progress">
                  {[0, 1, 2].map((i) => (
                    <i
                      key={i}
                      className={i <= run.question_index ? "filled" : ""}
                    />
                  ))}
                </div>
                {feedback && (
                  <p className="quest-feedback" role="status">
                    {feedback}
                  </p>
                )}
                <h3>{run.question?.prompt}</h3>
                <div className="quest-answers">
                  {run.question?.options.map((answer, i) => (
                    <button
                      key={answer}
                      disabled={busy || run.question?.tried.includes(answer)}
                      onClick={() => chooseAnswer(answer)}
                    >
                      <span>{["A", "B", "C"][i]}</span>
                      {answer}
                      <ArrowRight size={18} />
                    </button>
                  ))}
                </div>
                <p className="quest-muted">
                  {run.question?.tried.length
                    ? "Дұрыс жауапқа 10 ұпай"
                    : "Бірінші талпыныста 30 ұпай"}{" "}
                  · аяқтағаныңа +10
                </p>
              </div>
            ))}
          {error && (
            <div className="quest-error" role="alert">
              {error}
            </div>
          )}
          {busy && (
            <div className="quest-busy" role="status">
              Сақталуда…
            </div>
          )}
        </QuestDialog>
      )}
      <div className="quest-sr-only">{PLOTS.length} құрылыс орны бар.</div>
    </main>
  );
}
