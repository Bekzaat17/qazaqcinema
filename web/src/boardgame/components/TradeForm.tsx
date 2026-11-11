import { useState } from "react";
import { ArrowLeftRight, Send } from "../../ui-kit/adapters/icons";
import { groupIndices } from "../rules";
import { money } from "../format";
import type { Board, Match } from "../types";

export default function TradeForm({ board, match, buyer, disabled, initialAmount, initialGive = -1,
  label = "Ұсыныс жіберу", onSubmit, exchange, intent = "counter" }:
  { board: Board; match: Match; buyer: number; disabled: boolean; initialAmount: number;
    initialGive?: number; label?: string; exchange?: boolean; intent?: "buy" | "sell" | "counter"; onSubmit: (amount: number, give: number) => void }) {
  const [amount, setAmount] = useState(String(initialAmount));
  const [give, setGive] = useState(initialGive);
  const available = board.tiles.flatMap((tile, i) => {
    const lot = match.lots[i];
    return lot?.owner === buyer && !lot.level && !lot.mortgaged
      && !groupIndices(board, i).some((j) => match.lots[j]?.level)
      ? [{ tile, index: i }] : [];
  });
  const valid = Number.isInteger(Number(amount)) && Number(amount) >= (give < 0 ? 1 : 0)
    && Number(amount) <= match.players[buyer].cash && Number(amount) <= 1000000
    && (give === -1 || available.some((item) => item.index === give)) && (!exchange || give >= 0);
  return <div className="dala-trade-form">
    <label>{exchange ? "Қосымша монета (0 — үстемесіз)" : "Баға, Dala монетасы"}
      <input type="number" min={give < 0 ? 1 : 0} max={match.players[buyer].cash}
        value={amount} onChange={(event) => setAmount(event.target.value)} />
    </label>
    {exchange !== false && <label><ArrowLeftRight size={14} /> {match.players[buyer].name} беретін кәсіп
      <select value={give} onChange={(event) => setGive(Number(event.target.value))}>
        <option value={-1}>{exchange ? "Кәсіпті таңда" : "Тек монетамен"}</option>
        {available.map(({ tile, index }) => <option key={index} value={index}>{tile.name} · {money(tile.price)}</option>)}
      </select>
    </label>}
    <button type="button" className={`dala-primary ${intent === "buy" ? "dala-action-buy" : intent === "sell" ? "dala-action-sell" : ""}`} disabled={disabled || !valid || match.phase === "debt"}
      onClick={() => onSubmit(Number(amount), give)}><Send size={16} /> {label}</button>
  </div>;
}
