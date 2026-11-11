import AppearancePicker from "./AppearancePicker";
import type { PlayerAppearance, Portrait } from "../../ui-kit/PlayerAvatar";
import { GameCoin, YurtIcon } from "../../ui-kit/GameIcons";
import CoinAmount from "./CoinAmount";
import {
  ArrowRight,
  DoorOpen,
  Gamepad2,
  Users,
  Bot,
  MapPin,
  ChevronRight,
  Check,
} from "../../ui-kit/adapters/icons";
import type { Board, Catalog, RoomView, Scenario } from "../types";
import BoardArt from "./BoardArt";
import { roundLimitLabel } from "../format";
export default function HomeScreen({
  catalog,
  appearance,
  onPortrait,
  board,
  scenario,
  view,
  scenarioId,
  name,
  busy,
  practice,
  setName,
  setBoardId,
  setScenarioId,
  setScreen,
  setPanel,
  setLearning,
  requestCreate,
}: {
  catalog: Catalog;
  appearance: PlayerAppearance;
  onPortrait: (value: Portrait) => void;
  board: Board;
  scenario: Scenario | undefined;
  view: RoomView | null;
  scenarioId: string;
  name: string;
  busy: boolean;
  practice: boolean;
  setName: (value: string) => void;
  setBoardId: (value: string) => void;
  setScenarioId: (value: string) => void;
  setScreen: (value: "room") => void;
  setPanel: (value: "telegram" | "join" | "rooms" | "create") => void;
  setLearning: (value: boolean) => void;
  requestCreate: () => void;
}) {
  return (
    <>
      <section className="dala-intro">
        <span className="dala-eyebrow">
          <i /> ҚАЗАҚША · ДОСТАРМЕН · БОТТАРМЕН
        </span>
        <h1>
          Өз жолың.
          <br />
          <em>Өз дәулетің.</em>
        </h1>
        <p>
          Кубик лақтыр. Кәсіп сатып ал.
          <br />
          Достарыңмен бір үстел басында жарыс.
        </p>
        <div className="dala-intro-actions">
          {view && (
            <button className="dala-primary" onClick={() => setScreen("room")}>
              <DoorOpen size={17} /> Бөлмеге оралу
            </button>
          )}
          <button className="dala-primary" onClick={() => setPanel("create")}><Users size={18} /> Бөлме құру</button>
          <button className="dala-secondary" onClick={() => setPanel("rooms")}><DoorOpen size={18} /> Бөлме табу</button>
          <button
            className={view ? "dala-secondary" : "dala-primary"}
            onClick={() =>
              document
                .getElementById("dala-setup")
                ?.scrollIntoView({ behavior: "smooth", block: "start" })
            }
          >
            <Gamepad2 size={18} /> {practice ? "Боттармен жаттығу" : "Карта мен режимді таңдау"}
          </button>
        </div>
        <div className="dala-badges">
          <span>
            <Users size={16} /> 2–4 ойыншы
          </span>
          <span>
            <Bot size={16} /> Боттармен де болады
          </span>
          <span>
            <MapPin size={16} /> {catalog.boards.length} өлке
          </span>
        </div>
        <div className="dala-currency-note"><GameCoin size={22} />
          <span><b>Dala</b> — ойын монетасы<small>Тек ойын ішінде · нақты ақша емес</small></span>
        </div>
      </section>
      <div className="dala-preview-caption">
        <span className="dala-eyebrow">АЛАҢНЫҢ КӨРІНІСІ</span>
        <h2>{board.name}</h2>
        <p>{board.subtitle}</p>
      </div>
      <section className="dala-village-entry" aria-labelledby="dala-village-title">
        <div className="dala-village-landscape" aria-hidden="true">
          <svg viewBox="0 0 400 220" fill="none">
            <circle cx="302" cy="47" r="25" fill="#f7dfa0" />
            <path d="M0 146 82 40 154 124 225 65 340 151 400 98V220H0Z" fill="#9aafa0" />
            <path d="m57 73 25-33 30 35-26-10Z" fill="#f2efdc" />
            <path d="M0 172Q90 116 200 158T400 150V220H0Z" fill="#79966b" />
            <ellipse cx="209" cy="197" rx="140" ry="19" fill="#526d4b" opacity=".22" />
            <path d="m158 218 47-57 35 5-43 52" fill="#d3bf8a" />
            <path d="M119 147q54-30 108 0v39q-54 28-108 0Z" fill="#f5e6bb" />
            <path d="m108 148 64-61 67 61q-65 29-131 0Z" fill="#c77c57" />
            <ellipse cx="173" cy="91" rx="12" ry="4" fill="#f3d28a" />
            <path d="M119 163q54 25 108 0" stroke="#ad6950" strokeWidth="6" />
            <path d="M164 193v-35q11-7 22 0v35" fill="#3b6860" />
            <path d="m151 200 25-6 24 8-26 7Z" fill="#b56e50" />
            <path d="M284 167v-50m-22 29 22-49 24 49m-51 17 27-48 29 48" stroke="#405f4c" strokeWidth="7" strokeLinejoin="round" />
            <path d="M72 191v-51m-22 28 22-48 24 48m-51 17 27-48 29 48" stroke="#4b7155" strokeWidth="7" strokeLinejoin="round" />
            <path d="M267 199h77m-67-14v24m29-29v29m29-30v30" stroke="#d9bc80" strokeWidth="4" strokeLinecap="round" />
            <g fill="#e4bf76"><circle cx="114" cy="201" r="3" /><circle cx="250" cy="185" r="3" /><circle cx="238" cy="201" r="3" /></g>
          </svg>
        </div>
        <div className="dala-village-copy">
          <span className="dala-eyebrow">БІР ӘЛЕМ · ЕКІ ОЙЫН</span>
          <h2 id="dala-village-title">Партия арасында — өз ауылың.</h2>
          <p>Үстелде кәсіп құр. Ауылда киіз үй салып, құдық қаз, шеберханаңды дамыт.
            Рухтардың қазақша тапсырмаларын орындап, құрылысқа материал жина.</p>
          <div className="dala-village-features">
            <span>3 ғимарат · 9 даму сатысы</span>
            <span>Ауылың әр кіргенде сақталады</span>
          </div>
          <button className="dala-primary" onClick={() => setLearning(true)}>
            <YurtIcon size={19} /> Менің ауылыма бару <ArrowRight size={17} />
          </button>
          <small>Партия монетасы мен ауыл материалдары бөлек. Telegram-да рейтинг ортақ.</small>
        </div>
      </section>
      <section className="dala-setup" id="dala-setup">
        <div className="dala-section-title">
          <div>
            <span className="dala-eyebrow">ӘР ПАРТИЯ — ЖАҢА ХИКАЯ</span>
            <h2>Қай өлкеде бастаймыз?</h2>
          </div>
          <span>{catalog.scenarios.length} дайын сценарий</span>
        </div>
        <div className="dala-board-cards">
          {catalog.boards.map((item, i) => (
            <button
              key={item.id}
              className={`dala-board-card ${board.id === item.id ? "selected" : ""}`}
              onClick={() => {
                setBoardId(item.id);
                setScenarioId(
                  (catalog.scenarios.find((s) => s.board === item.id && s.round_limit === scenario?.round_limit)
                    ?? catalog.scenarios.find((s) => s.board === item.id))!.id,
                );
              }}
              aria-pressed={board.id === item.id}
            >
              <BoardArt board={item} />
              <span className="dala-board-number">0{i + 1}</span>
              <h3>{item.name}</h3>
              <p>{item.subtitle}</p>
              <span className="dala-board-card-bottom">
                {item.tiles.length} ұяшық <ChevronRight size={16} />
              </span>
            </button>
          ))}
        </div>
        <div className="dala-setup-grid">
          <div>
            <span className="dala-eyebrow">ПАРТИЯНЫҢ ЫРҒАҒЫ</span>
            <div className="dala-scenario-options">
              {catalog.scenarios
                .filter((s) => s.board === board.id)
                .map((option, i) => (
                  <button
                    key={option.id}
                    aria-pressed={scenarioId === option.id}
                    onClick={() => setScenarioId(option.id)}
                  >
                    <span>
                      {["Алғашқы капитал", "Сауда дәуірі", "Іскерлер жарысы", "Соңғы ойыншыға дейін"][
                        i
                      ] ?? option.name}
                    </span>
                    <small>
                      {roundLimitLabel(option.round_limit)} ·{" "}
                      <CoinAmount value={option.starting_cash} />
                    </small>
                    <i>
                      {scenarioId === option.id ? <Check size={15} /> : null}
                    </i>
                  </button>
                ))}
            </div>
            <p className="dala-muted">{scenario?.story}</p>
          </div>
          <div className="dala-start-card">
            <label htmlFor="dala-name">Ойындағы атың</label>
            <input
              id="dala-name"
              value={name}
              maxLength={24}
              onChange={(e) => setName(e.target.value)}
              placeholder="Атыңды жаз"
            />
            <AppearancePicker appearance={appearance} onChange={onPortrait} />
            <button
              className="dala-primary dala-full"
              disabled={busy || !name.trim()}
              onClick={() => practice ? requestCreate() : setPanel("create")}
            >
              {practice ? <Bot size={18} /> : <DoorOpen size={18} />}
              {practice ? "Боттармен жаттығу" : "Бөлме құру"}
            </button>
            <button
              className="dala-secondary dala-full"
              onClick={() => setPanel("rooms")}
            >
              <DoorOpen size={17} /> Бөлме табу немесе кодпен кіру
            </button>
            <small>
              {practice
                ? "Жаттығу осы браузерде сақталады. Достармен ойнау үшін Telegram-нан аш."
                : "Бөлмеде достарды күт немесе бос орындарға бот қос."}
            </small>
          </div>
        </div>
      </section>
      <footer className="dala-footer">
        <a href="/games">Ойын туралы</a>
        <span>QazaqCinema әлемінен</span>
        <button onClick={() => setLearning(true)}>
          <YurtIcon size={14} /> Менің ауылым
        </button>
        <span>Құр. Дамыт. Гүлден.</span>
      </footer>
    </>
  );
}
