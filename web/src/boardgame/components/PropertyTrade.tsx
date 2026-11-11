import { useState } from "react";
import { ArrowLeftRight, ShoppingBag, Tag } from "../../ui-kit/adapters/icons";
import { groupIndices } from "../rules";
import type { Action, Board, Match } from "../types";
import TradeForm from "./TradeForm";

export type SendTrade = (kind: Action, target?: string, tile?: number, amount?: number, giveTile?: number) => void;
export default function PropertyTrade({ board, match, selected, me, disabled, send }:
  { board: Board; match: Match; selected: number; me: number; disabled: boolean; send: SendTrade }) {
  const [mode, setMode] = useState<"price" | "swap" | null>(null);
  const [buyer, setBuyer] = useState(() => match.players.findIndex((p, i) => i !== me && !p.bankrupt));
  const lot = match.lots[selected];
  const own = lot.owner === me;
  const blocked = disabled || lot.level > 0 || lot.mortgaged || match.phase === "debt"
    || groupIndices(board, selected).some((i) => (match.lots[i]?.level ?? 0) > 0);
  return <section className="dala-property-trade">
    <h4>{own ? "Бұл кәсіппен не істейміз?" : "Осы кәсіпті алғың келе ме?"}</h4>
    <div className="dala-trade-choice">
      <button className={`dala-primary ${own ? "dala-action-sell" : "dala-action-buy"}`} disabled={blocked}
        aria-pressed={mode === "price"} onClick={() => setMode(mode === "price" ? null : "price")}>
        {own ? <Tag size={17} /> : <ShoppingBag size={17} />}{own ? "Сату" : "Сатып алу"}
      </button>
      <button className="dala-secondary" disabled={blocked} aria-pressed={mode === "swap"}
        onClick={() => setMode(mode === "swap" ? null : "swap")}><ArrowLeftRight size={17} /> Айырбастау</button>
    </div>
    {blocked && <small>{match.phase === "debt" ? "Алдымен қарызды өте." : disabled ? "Ағымдағы әрекеттің аяқталуын күт." : "Алдымен кепілді алып, осы топтағы құрылыстарды сат."}</small>}
    {mode && !blocked && <div className="dala-trade-details">
      <p className="dala-trade-explanation">{own ? `Сен бересің: ${board.tiles[selected].name}. ${mode === "swap" ? "Орнына төмендегі кәсіп пен монетаны аласың." : "Төмендегі бағаға сатуды ұсынасың."}` : `Сен аласың: ${board.tiles[selected].name}. ${mode === "swap" ? "Орнына өз кәсібіңді және көрсетілген монетаны бересің." : "Төмендегі бағаны иесіне ұсынасың."}`}</p>
      {own && <label>Кімге ұсынамыз?
        <select value={buyer} onChange={(e) => setBuyer(Number(e.target.value))}>
          {match.players.map((p, i) => i !== me && !p.bankrupt ? <option key={p.id} value={i}>{p.name}</option> : null)}
        </select>
      </label>}
      <TradeForm key={`${mode}:${buyer}`} board={board} match={match} buyer={own ? buyer : me}
        disabled={blocked} exchange={mode === "swap"} intent={mode === "swap" ? "counter" : own ? "sell" : "buy"}
        initialAmount={mode === "swap" ? 0 : board.tiles[selected].price}
        label={mode === "swap" ? "Айырбас ұсыну" : own ? "Бағаны ұсыну" : "Сатып алуды ұсыну"}
        onSubmit={(amount, give) => send(own ? "ask" : "offer", own ? match.players[buyer].id : "", selected, amount, give)} />
      <small>Ұсыныс жіберіледі. Адам өзі келіседі немесе қарсы баға ұсынады.</small>
    </div>}
  </section>;
}
