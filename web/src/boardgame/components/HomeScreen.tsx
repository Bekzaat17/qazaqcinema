import {
  ArrowRight,
  Flag,
  Dices,
  Users,
  Sparkles,
  MapPin,
  ChevronRight,
  Check,
  Plus,
  Ticket,
  ScrollText,
} from "lucide-react";
import type { Board, Catalog, RoomView, Scenario } from "../types";
import { money } from "../format";
import BoardArt from "./BoardArt";
export default function HomeScreen({
  catalog,
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
  setPanel: (value: "telegram" | "join") => void;
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
              <Flag size={17} /> Бөлмеге оралу
            </button>
          )}
          <button
            className={view ? "dala-secondary" : "dala-primary"}
            onClick={() =>
              document
                .getElementById("dala-setup")
                ?.scrollIntoView({ behavior: "smooth", block: "start" })
            }
          >
            <Dices size={18} /> Ойынды бастау <ArrowRight size={17} />
          </button>
        </div>
        <div className="dala-badges">
          <span>
            <Users size={16} /> 2–4 ойыншы
          </span>
          <span>
            <Sparkles size={16} /> Боттармен де болады
          </span>
          <span>
            <MapPin size={16} /> {catalog.boards.length} өлке
          </span>
        </div>
        <small>Орнатусыз. Графика құрылғыңда.</small>
      </section>
      <div className="dala-preview-caption">
        <span className="dala-eyebrow">АЛАҢНЫҢ КӨРІНІСІ</span>
        <h2>{board.name}</h2>
        <p>{board.subtitle}</p>
      </div>
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
                  catalog.scenarios.find((s) => s.board === item.id)!.id,
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
                      {["Алғашқы капитал", "Сауда дәуірі", "Іскерлер жарысы"][
                        i
                      ] ?? option.name}
                    </span>
                    <small>
                      {option.round_limit} айналым ·{" "}
                      {money(option.starting_cash)}
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
            <button
              className="dala-primary dala-full"
              disabled={busy || !name.trim()}
              onClick={requestCreate}
            >
              <Plus size={18} />
              {practice ? "Боттармен жаттығу" : "Бөлме құру"}
            </button>
            <button
              className="dala-secondary dala-full"
              onClick={() => setPanel(practice ? "telegram" : "join")}
            >
              <Ticket size={17} /> Достардың бөлмесіне кіру
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
        <span>QazaqCinema әлемінен</span>
        <button onClick={() => setLearning(true)}>
          <ScrollText size={14} /> Тіл мектебі
        </button>
        <span>Құр. Дамыт. Гүлден.</span>
      </footer>
    </>
  );
}
