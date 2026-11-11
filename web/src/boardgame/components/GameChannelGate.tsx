import { useEffect, useState } from "react";
import { Megaphone, RefreshCw } from "../../ui-kit/adapters/icons";
import { BOT_URL, openTelegramLink } from "../../lib/telegram";
import type { GameGateway } from "../gateway";
import type { GameAccess } from "../types";

export default function GameChannelGate({ gateway, onAllowed }: { gateway: GameGateway; onAllowed: () => void }) {
  const [access, setAccess] = useState<GameAccess | null>(null), [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const check = async () => {
    setBusy(true); setError("");
    try {
      const status = await gateway.access(); setAccess(status);
      if (status.allowed) onAllowed();
      else setError(gateway.practice ? "" : "Жазылым әлі расталмады. Арнаға қосылып, қайта тексер.");
    } catch { setError("Байланысты тексеріп, қайта көр."); }
    finally { setBusy(false); }
  };
  useEffect(() => {
    let active = true;
    void gateway.access().then((status) => { if (active) setAccess(status); }).catch(() => { if (active) setError("Байланысты тексеріп, қайта көр."); });
    return () => { active = false; };
  }, [gateway]);
  return <div className="dala-room-empty">
    <Megaphone size={34} /><h3>Ойынды бірге жалғастырайық</h3>
    <p>Алғашқы 3 партияны ойнадың. Келесі партиялар үшін Telegram арнамызға жазыл. Ақша төлеудің қажеті жоқ.</p>
    {gateway.practice ? <>
      <p>Браузердегі жаттығу лимиті аяқталды. Telegram-да кіріп, арнаға жазылуыңды сол жерде раста.</p>
      <button className="dala-primary dala-full" onClick={() => openTelegramLink(`${BOT_URL}?startapp=quest`)}>Telegram-да жалғастыру</button>
    </> : <>
      {access?.channel_url && <button className="dala-primary dala-full" onClick={() => openTelegramLink(access.channel_url)}>Арнаға жазылу</button>}
      <button className="dala-secondary dala-full" disabled={busy} onClick={() => void check()}><RefreshCw size={17} />{busy ? "Тексерілуде…" : "Жазылымды тексеру"}</button>
    </>}
    {error && <p role="status">{error}</p>}
    <small>Басталған партияң сақталады. Оны соңына дейін ойнай аласың.</small>
  </div>;
}
