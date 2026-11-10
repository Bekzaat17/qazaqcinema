import type { CSSProperties } from "react";
import {
  Copy,
  Plus,
  Check,
  X,
  Dices,
  ArrowRight,
  DoorOpen,
} from "lucide-react";
import { BOT_URL } from "../../lib/telegram";
import { money } from "../format";
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
  onLeave: () => void;
}) {
  const room = view.room;
  return (
    <section className="dala-lobby">
      <div className="dala-lobby-panel">
        <span className="dala-eyebrow">БІР ҮСТЕЛ · ОРТАҚ ПАРТИЯ</span>
        <h1>Достарды жина.</h1>
        <p>
          {practice
            ? "Жаттығуда бос орындарға бот қосып бастай аласың."
            : "Бөлме кодын бөліс немесе шақыру сілтемесін достарыңа жібер."}
        </p>
        <div className="dala-room-code">
          <div>
            <small>{practice ? "ЖЕРГІЛІКТІ ЖАТТЫҒУ" : "БӨЛМЕ КОДЫ"}</small>
            <b>{practice ? "Боттармен" : view!.code}</b>
          </div>
          {!practice && (
            <button
              className="dala-icon"
              aria-label="Шақыру сілтемесін көшіру"
              onClick={copyInvite}
            >
              <Copy size={18} />
            </button>
          )}
        </div>
        {!practice && (
          <input
            className="dala-invite-url"
            readOnly
            aria-label="Шақыру сілтемесі"
            value={`${BOT_URL}?startapp=quest_room_${view!.code}`}
            onFocus={(e) => e.target.select()}
          />
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
                  {seat ? seat.name[0] : <Plus size={20} />}
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
            <div className="dala-add-bots">
              {catalog.bots
                .filter((bot) => !room.seats.some((s) => s.bot === bot.id))
                .map((bot) => (
                  <button
                    className="dala-secondary"
                    key={bot.id}
                    disabled={busy || room.seats.length >= 4}
                    onClick={() => send("add_bot", bot.id)}
                  >
                    <Plus size={15} />
                    {bot.name} бот
                  </button>
                ))}
            </div>
            <button
              className="dala-primary dala-full"
              disabled={
                busy ||
                room.seats.length < 2 ||
                !room.seats.every((s) => s.ready || s.id === room.host)
              }
              onClick={() => send("start")}
            >
              <Dices size={19} /> Партияны бастау <ArrowRight size={17} />
            </button>
          </>
        ) : (
          <button
            className="dala-primary dala-full"
            disabled={busy}
            onClick={() => send("ready")}
          >
            <Check size={18} />
            {room.seats.find((s) => s.id === view?.me)?.ready
              ? "Дайын емеспін"
              : "Мен дайынмын"}
          </button>
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
            <dd>{scenario?.round_limit} айналым</dd>
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
