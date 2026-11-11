import { useEffect, useState } from "react";
import { DoorOpen, RefreshCw, Search, Users } from "../../ui-kit/adapters/icons";
import { BOT_URL, openTelegramLink } from "../../lib/telegram";
import type { GameGateway } from "../gateway";
import type { Catalog, PublicRoom, ActiveRoom } from "../types";
import { roundLimitLabel } from "../format";

export default function RoomExplorer({ gateway, catalog, busy, onJoin, onCode, onCreate }:
  { gateway: GameGateway; catalog: Catalog; busy: boolean; onJoin: (code: string) => void;
    onCode: () => void; onCreate: () => void }) {
  const [rooms, setRooms] = useState<PublicRoom[]>([]);
  const [mine, setMine] = useState<ActiveRoom[]>([]);
  const [loading, setLoading] = useState(true), [error, setError] = useState(false);
  const [reload, setReload] = useState(0);
  const available = rooms.filter((room) => !mine.some((own) => own.code === room.code));
  useEffect(() => {
    if (gateway.practice) return;
    const abort = new AbortController();
    let pending = false;
    const refresh = async () => {
      if (pending || document.hidden) return;
      pending = true;
      try {
        const [result, personal] = await Promise.all([gateway.publicRooms(abort.signal), gateway.myRooms(abort.signal)]);
        if (!abort.signal.aborted) { setRooms(result); setMine(personal); setError(false); }
      } catch {
        if (!abort.signal.aborted) setError(true);
      } finally {
        pending = false;
        if (!abort.signal.aborted) setLoading(false);
      }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 10000);
    return () => { abort.abort(); window.clearInterval(timer); };
  }, [gateway, reload]);
  return <div className="dala-room-explorer">
    <p className="dala-muted">Тізімнен бос бөлмені таңда. Досың сілтеме не код жіберсе, кодпен кір.</p>
    <div className="dala-room-entry-actions">
      <button className="dala-secondary" onClick={onCode}><DoorOpen size={17} /> Кодпен кіру</button>
      <button className="dala-primary" onClick={onCreate}><Users size={17} /> Бөлме құру</button>
    </div>
    {gateway.practice ? <div className="dala-room-empty">
      <Search size={32} /><h3>Ойыншыларды Telegram-нан тап</h3>
      <p>Ашық бөлмелер мен достармен ортақ ойын Telegram ішінде жұмыс істейді. Осы браузердегі жаттығу бөлек сақталады.</p>
      <button className="dala-primary" onClick={() => openTelegramLink(`${BOT_URL}?startapp=quest_rooms`)}>Telegram-да бөлмелерді ашу</button>
    </div> : <>
      {mine.length > 0 && <><h3>Менің бөлмелерім</h3><div className="dala-public-rooms">{mine.map((room) => <article key={room.code}><div><h3>{room.host_name} бөлмесі</h3><p>{room.started ? "Партия жүріп жатыр · прогресс сақталған" : "Ойыншыларды күтеміз"} · {room.players}/4</p><small>{room.code}</small></div><button className="dala-primary" disabled={busy} onClick={() => onJoin(room.code)}>Жалғастыру</button></article>)}</div></>}
      <div className="dala-room-list-heading"><b>Ашық бөлмелер</b><button className="dala-text-button" disabled={loading} onClick={() => { setLoading(true); setReload((r) => r + 1); }}><RefreshCw size={15} /> Жаңарту</button></div>
      {loading && <p role="status">Бөлмелерді іздеп жатырмыз…</p>}
      {error && <p role="alert">Тізім жаңармады. Байланысты тексеріп, қайта көр.</p>}
      {!loading && !error && !available.length && <div className="dala-room-empty"><Users size={30} /><h3>{mine.length ? "Басқа ашық бөлме жоқ" : "Әзірге ашық бөлме жоқ"}</h3><p>Ашық бөлме құр. Басқа ойыншылар сені осы тізімнен табады.</p><button className="dala-primary" onClick={onCreate}>Ашық бөлме құру</button></div>}
      <div className="dala-public-rooms">{available.map((room) => {
        const scenario = [...catalog.scenarios, ...(catalog.legacy_catalogs?.flatMap((c) => c.scenarios) ?? [])].find((s) => s.id === room.scenario_id);
        const board = catalog.boards.find((b) => b.id === scenario?.board);
        return <article key={room.code}>
          <div><span>{board?.name ?? "Ойын алаңы"}</span><h3>{room.host_name} бөлмесі</h3><p>{scenario ? roundLimitLabel(scenario.round_limit) : ""} · {room.players}/4 ойыншы</p><small>{4 - room.players} бос орын · ойын басталмаған</small></div>
          <button className="dala-primary" disabled={busy} onClick={() => onJoin(room.code)}><DoorOpen size={16} /> Кіру</button>
        </article>;
      })}</div>
    </>}
  </div>;
}
