import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Compass,
  Gem,
  HelpCircle,
  Leaf,
  Mountain,
  Settings2,
  Sparkles,
  TentTree,
  TreePine,
  Trophy,
  WandSparkles,
} from "lucide-react";
import { ApiError, NetworkError, SessionExpiredError } from "../lib/api";
import {
  BOT_URL,
  getInitData,
  getWebApp,
  haptic,
  openTelegramLink,
  showBackButton,
} from "../lib/telegram";
import QuestDialog from "./components/QuestDialog";
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

type Panel = "village" | "ranking" | "help" | "lesson" | null;

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

export default function QuestApp() {
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
    document.title = "QazaqQuest — Өз ауылыңды құр";
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
      else navigateApp("cinema");
    });
  }, [panel, playing]);

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
        if (result.run.complete) engine.current?.cast();
      }
    });
  };
  const build = (building: Building) =>
    void perform(async () => {
      setProgress(await gateway.build(building));
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
  const nextQuest = SHRINES.find(
    (target) => !progress?.completed_today.includes(target.id as QuestId),
  );
  const villageLevel =
    progress?.buildings.reduce((sum, building) => sum + building.level, 0) ?? 0;

  return (
    <main className={`quest-app ${playing ? "is-playing" : "is-intro"}`}>
      <div className="quest-world" ref={host} />
      {!playing && <div className="quest-world-wash" />}
      <header className="quest-header">
        <a
          className="quest-brand"
          href="/quest"
          aria-label="QazaqQuest"
          onClick={(event) => {
            event.preventDefault();
            setPanel(null);
            setPlaying(false);
          }}
        >
          <span className="quest-brand-icon">
            <Sparkles size={24} />
          </span>
          <span>
            Qazaq<span>Quest</span>
            <small>ТУҒАН ЖЕРДІҢ СИҚЫРЫ</small>
          </span>
        </a>
        <nav aria-label="Ойын мәзірі">
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
            <ArrowLeft size={15} />
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
              Қазақша үйреніп, арманыңдағы ауылды құр.
            </p>
            <div className="quest-intro-actions">
              <button
                className="quest-primary quest-play"
                disabled={!progress || busy}
                onClick={() => {
                  setPlaying(true);
                  setError("");
                  haptic.medium();
                }}
              >
                <WandSparkles size={21} />
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
            <div className="quest-intro-stats">
              <span>
                <TentTree size={20} />
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
              <div className="quest-wallet">
                <span title="Ағаш">
                  <TreePine size={18} />
                  <b>{progress.wood}</b>
                </span>
                <span title="Тас">
                  <Mountain size={18} />
                  <b>{progress.stone}</b>
                </span>
              </div>
            </div>
            <aside className="quest-missions">
              <div className="quest-card-label">
                <Compass size={15} /> БҮГІНГІ САЯХАТ{" "}
                <span>{progress.completed_today.length}/3</span>
              </div>
              {SHRINES.map((target, index) => {
                const done = progress.completed_today.includes(
                  target.id as QuestId,
                );
                const locked =
                  index > 0 &&
                  !progress.completed_quests.includes(
                    SHRINES[index - 1].id as QuestId,
                  );
                return (
                  <button
                    key={target.id}
                    className={`quest-mission ${done ? "is-done" : ""}`}
                    disabled={done || locked}
                    onClick={() => {
                      engine.current?.goTo(target);
                      setFeedback("");
                    }}
                  >
                    <span
                      className="quest-spirit-dot"
                      style={{ background: target.color }}
                    >
                      {done ? <Check size={14} /> : index + 1}
                    </span>
                    <span>
                      <b>{target.name}</b>
                      <small>
                        {done
                          ? "Бүгін оянды"
                          : locked
                            ? "Алдыңғы рухты оят"
                            : "100 ұпайға дейін · бару"}
                      </small>
                    </span>
                    {!done && !locked && <ArrowRight size={15} />}
                  </button>
                );
              })}
              {!nextQuest && (
                <p className="quest-all-done">
                  Үш рух оянды! Ауылыңды дамыт. Ертең жаңа ұпай жинай аласың.
                </p>
              )}
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
                <TentTree size={22} />
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
                  <WandSparkles size={30} />
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
          title={
            {
              village: "Менің ауылым",
              ranking: "Үздік саяхатшылар",
              help: "Алғашқы қадамың",
              lesson: run?.complete
                ? "Рух оянды!"
                : (near?.name ?? "Рухтың сынағы"),
            }[panel]
          }
          onClose={closePanel}
        >
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
                  қолдан. Тапсырманы бассаң, кейіпкер сол жаққа жүреді.
                </li>
                <li>
                  <b>Үйрен.</b> Рухқа жақындап, сиқыр батырмасын немесе E бас.
                  Үш сұраққа жауап бер.
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
              <p className="quest-muted">
                Әр ғимараттың үш деңгейі бар. Рухтарға көмектесіп, ауылға
                материал жина.
              </p>
              <div className="quest-materials">
                <span>
                  <TreePine size={18} /> {progress.wood} ағаш
                </span>
                <span>
                  <Mountain size={18} /> {progress.stone} тас
                </span>
              </div>
              <div className="quest-buildings">
                {progress.buildings.map((building, index) => {
                  const max = building.wood_cost === null;
                  const affordable =
                    !max &&
                    progress.wood >= building.wood_cost! &&
                    progress.stone >= building.stone_cost!;
                  return (
                    <article key={building.id}>
                      <div
                        className={`quest-building-art building-${building.id}`}
                      >
                        <TentTree size={36 + index * 2} strokeWidth={1.4} />
                        <span>{building.level || "+"}</span>
                      </div>
                      <div>
                        <h3>{building.name}</h3>
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
                          <small className="quest-cost-note">
                            Материал жинау керек
                          </small>
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
                <h3>Алқапқа жарық оралды</h3>
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
                  Марапат бір рет есептеледі.
                  {gateway.practice
                    ? " Бұл — жаттығу нәтижесі."
                    : " Прогресс сақталды."}
                </p>
                <button
                  className="quest-primary"
                  onClick={() => {
                    setPanel("village");
                    setFeedback("");
                  }}
                >
                  Ауылымды дамыту <TentTree size={20} />
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
