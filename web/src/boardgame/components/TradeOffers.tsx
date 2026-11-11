import { useState } from "react";
import { Check, ArrowLeftRight, X, Undo2 } from "../../ui-kit/adapters/icons";
import { offerSender, offerRecipient } from "../rules";
import { money } from "../format";
import type { Action, Board, Match } from "../types";
import TradeForm from "./TradeForm";

export default function TradeOffers({ board, match, me, disabled, send }:
  { board: Board; match: Match; me: number; disabled: boolean;
    send: (kind: Action, target?: string, tile?: number, amount?: number, giveTile?: number) => void }) {
  const [counter, setCounter] = useState("");
  const offers = match.offers.filter((offer) => offer.buyer === me || offer.seller === me);
  return <div className="dala-trade-list">
    <p className="dala-muted">Сатып ал, сат немесе кәсіпке кәсіп айырбаста. Қарсы ұсыныспен саудаласуға болады.</p>
    {offers.length ? offers.map((offer) => {
      const sender = offerSender(offer), recipient = offerRecipient(offer);
      const incoming = recipient === me;
      return <article key={offer.id}>
        <span className="dala-eyebrow">{incoming ? `${match.players[sender].name} ҰСЫНЫСЫ` : "СЕНІҢ ҰСЫНЫСЫҢ"}</span>
        <h3>{board.tiles[offer.tile].name}</h3>
        <p>{offer.buyer === me ? "Сен аласың" : "Сен бересің"}: {board.tiles[offer.tile].name}</p>
        {(offer.give_tile ?? -1) >= 0 && <p className="dala-exchange-line"><ArrowLeftRight size={16} /> {offer.buyer === me ? "Сен бересің" : "Сен аласың"}: {board.tiles[offer.give_tile!].name}</p>}
        <b>{offer.amount ? `${offer.buyer === me ? "Сен төлейсің" : "Сен аласың"}: ${money(offer.amount)}` : "Үстемесіз айырбас"}</b>
        <small>{offer.expires}-айналымға дейін · бір белсенді ұсыныс</small>
        <div className="dala-offer-actions">
          {incoming ? <>
            <button className="dala-primary dala-action-buy" disabled={disabled} onClick={() => send("accept", offer.id)}><Check size={16} /> Қабылдау</button>
            <button className="dala-secondary" disabled={disabled} onClick={() => setCounter(counter === offer.id ? "" : offer.id)}><ArrowLeftRight size={16} /> Саудаласу</button>
            <button className="dala-secondary dala-action-sell" disabled={disabled} onClick={() => send("reject", offer.id)}><X size={15} /> Бас тарту</button>
          </> : <button className="dala-secondary" disabled={disabled} onClick={() => send("withdraw", offer.id)}><Undo2 size={16} /> Ұсынысты қайтару</button>}
        </div>
        {incoming && counter === offer.id && <TradeForm key={offer.id} board={board} match={match}
          buyer={offer.buyer} disabled={disabled} initialAmount={offer.amount} initialGive={offer.give_tile ?? -1}
          label="Қарсы ұсыныс" onSubmit={(amount, give) => { send("counter", offer.id, -1, amount, give); setCounter(""); }} />}
      </article>;
    }) : <p className="dala-empty">Ұсыныс жоқ. Кәсіп карточкасынан сатып алуды немесе айырбасты ұсын.</p>}
  </div>;
}
