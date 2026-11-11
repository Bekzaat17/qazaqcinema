import PlayerAvatar from "../../ui-kit/PlayerAvatar";
import { playerAppearance } from "../appearance";
import type { CSSProperties } from "react";
import {
  Copy,
  Plus,
  Check,
  X,
  Gamepad2,
  Bot,
  ArrowRight,
  DoorOpen,
  Send,
  Globe2,
  LockKeyhole,
} from "../../ui-kit/adapters/icons";
import { BOT_URL } from "../../lib/telegram";
import { money, roundLimitLabel } from "../format";
import type { Action, Board, Catalog, RoomView, Scenario } from "../types";
import BoardArt from "./BoardArt";
export default function LobbyScreen({
  catalog,
  board,
  scenario,
  view,
  busy,
  practice,
  send,
  copyInvite,
  copyCode,
  shareInvite,
  setVisibility,
  onLeave,
}: {
  catalog: Catalog;
  board: Board;
  scenario: Scenario | undefined;
  view: RoomView;
  busy: boolean;
  practice: boolean;
  send: (kind: Action, target?: string, tile?: number, amount?: number) => void;
  copyInvite: () => void;
  copyCode: () => void;
  shareInvite: () => void;
  setVisibility: (value: boolean) => void;
  onLeave: () => void;
}) {
  const room = view.room;
  const isHost = room.host === view.me;
  const waiting = room.seats.filter((s) => !s.bot && s.id !== room.host && !s.ready);
  const canStart = room.seats.length >= 2 && !waiting.length;
  const ready = room.seats.find((s) => s.id === view.me)?.ready;
  return (
    <section className="dala-lobby">
      <div className="dala-lobby-panel">
        <span className="dala-eyebrow">БІР ҮСТЕЛ · ОРТАҚ ПАРТИЯ</span>
        <h1>{practice ? "Боттармен жаттығу" : "Ойын алдындағы бөлме"}</h1>
        <p>
          {practice
            ? "Жаттығуда бос орындарға бот қосып бастай аласың."
            : "Бөлме кодын бөліс немесе шақыру сілтемесін достарыңа жібер."}
        </p>
        {!practice && <>
          <ol className="dala-room-steps"><li>1. Досыңды шақыр</li><li>2. Дайындықты раста</li><li>3. Ойынды баста</li></ol>
          <div className="dala-room-privacy"><span>{view.is_public ? <Globe2 size={17} /> : <LockKeyhole size={17} />}{view.is_public ? "Ашық бөлме · тізімде көрінеді" : "Достарға арналған · сілтеме не кодпен"}</span>
            {isHost && <label><input type="checkbox" checked={!!view.is_public} disabled={busy} onChange={(e) => setVisibility(e.target.checked)} /> Бәріне ашу</label>}
          </div>
          <button className="dala-primary dala-full" onClick={shareInvite}><Send size={18} /> Досымды шақыру</button>
          <div className="dala-room-entry-actions"><button className="dala-secondary" onClick={copyInvite}><Copy size={16} /> Сілтемені көшіру</button><button className="dala-secondary" onClick={copyCode}><Copy size={16} /> Кодты көшіру</button></div>
        </>}
        <div className="dala-room-code">
          <div>
            <small>{practice ? "ЖЕРГІЛІКТІ ЖАТТЫҒУ" : "БӨЛМЕ КОДЫ"}</small>
            <b>{practice ? "Боттармен" : view!.code}</b>
          </div>
        </div>
        {!practice && (
          <details className="dala-invite-details"><summary>Шақыру сілтемесі</summary><input
            className="dala-invite-url"
            readOnly
            aria-label="Шақыру сілтемесі"
            value={`${BOT_URL}?startapp=quest_room_${view!.code}`}
            onFocus={(e) => e.target.select()}
          /></details>
        )}
        <div className="dala-seats">
          {Array.from({ length: 4 }, (_, i) => {
            const seat = room.seats[i];
            return (
              <div
                key={seat?.id ?? i}
                className={`dala-seat ${seat ? "filled" : ""}`}
              >
                <span
                  className="dala-avatar"
                  style={
                    {
                      "--avatar": seat?.color ?? "#bcc8b1",
                    } as CSSProperties
                  }
                >
                  {seat ? <PlayerAvatar appearance={playerAppearance(seat, view.appearances)} color={seat.color} size={44} /> : <Plus size={20} />}
                </span>
                <div>
                  <b>{seat?.name ?? "Бос орын"}</b>
                  <small>
                    {seat
                      ? seat.bot
                        ? "Бот"
                        : seat.id === room.host
                          ? "Бөлме иесі"
                          : seat.ready
                            ? "Дайын"
                            : "Дайындалуда"
                      : "Досың немесе бот қосылады"}
                  </small>
                </div>
                {seat?.ready ? <Check size={18} /> : null}
                {seat?.bot && room.host === view?.me && (
                  <button
                    className="dala-icon"
                    aria-label={`${seat.name} ботын алып тастау`}
                    disabled={busy}
                    onClick={() => send("remove_bot", seat.id)}
                  >
                    <X size={15} />
                  </button>
                )}
              </div>
            );
          })}
        </div>
        {room.host === view?.me ? (
          <>
            <details className="dala-bot-picker"><summary><Bot size={16} /> Бос орынға бот қосу</summary><div className="dala-add-bots">
              {catalog.bots
                .filter((bot) => !room.seats.some((s) => s.bot === bot.id))
                .map((bot) => (
                  <button
                    className="dala-secondary"
                    key={bot.id}
                    disabled={busy || room.seats.length >= 4}
                    onClick={() => send("add_bot", bot.id)}
                  >
                    <Bot size={15} />
                    {bot.name} бот
                  </button>
                ))}
            </div></details>
            <p className="dala-ready-status" role="status">{canStart ? "Бәрі дайын. Ойынды бастауға болады!" : room.seats.length < 2 ? "Досыңды күт немесе бір бот қос. Кемінде 2 ойыншы керек." : `${waiting.map((s) => s.name).join(", ")} дайын екенін растауы керек.`}</p>
            <button
              className="dala-primary dala-full"
              disabled={
                busy ||
                !canStart
              }
              onClick={() => send("start")}
            >
              <Gamepad2 size={19} /> Партияны бастау <ArrowRight size={17} />
            </button>
          </>
        ) : (
          <><p className="dala-ready-status" role="status">{ready ? "Сен дайынсың. Ойынды бөлме иесі бастайды." : "Қосылдың! Дайын болсаң, төмендегі батырманы бас."}</p><button
            className={`${ready ? "dala-secondary" : "dala-primary"} dala-full`}
            disabled={busy}
            onClick={() => send("ready")}
          >
            <Check size={18} />
            {ready
              ? "Дайындықты қайтару"
              : "Мен дайынмын"}
          </button></>
        )}
        <button className="dala-text-button" onClick={onLeave}>
          <DoorOpen size={15} /> Бөлмеден шығу
        </button>
      </div>
      <aside className="dala-lobby-settings">
        <BoardArt board={board} />
        <span className="dala-eyebrow">ТАҢДАЛҒАН АЛАҢ</span>
        <h2>{board.name}</h2>
        <p>{scenario?.story}</p>
        <dl>
          <div>
            <dt>Партия</dt>
            <dd>{scenario ? roundLimitLabel(scenario.round_limit) : "—"}</dd>
          </div>
          <div>
            <dt>Бастапқы капитал</dt>
            <dd>{money(scenario?.starting_cash ?? 0)}</dd>
          </div>
          <div>
            <dt>Айналым табысы</dt>
            <dd>{money(scenario?.salary ?? 0)}</dd>
          </div>
        </dl>
        {room.host === view?.me && (
          <>
            <label htmlFor="dala-room-scenario">Сценарийді өзгерту</label>
            <select
              id="dala-room-scenario"
              value={room.scenario_id}
              disabled={busy}
              onChange={(e) => send("configure", e.target.value)}
            >
              {catalog.scenarios.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            <small>Өзгерткенде достар дайындығын қайта растайды.</small>
          </>
        )}
      </aside>
    </section>
  );
}
