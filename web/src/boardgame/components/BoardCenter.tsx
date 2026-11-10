import type { Board, Match } from "../types";
import { money } from "../format";

const PHASE_LABELS = {
  roll: "Кубик лақтыратын кез",
  buy: "Кәсіп сатып алу",
  end: "Жүрісті аяқтау",
  debt: "Қарызды өтеу",
  finished: "Партия аяқталды",
};

export default function BoardCenter({
  board,
  match,
  selected,
  onInspect,
}: {
  board: Board;
  match: Match | null;
  selected: number;
  onInspect: () => void;
}) {
  const player = match?.players[match.turn];
  const tile = board.tiles[selected];
  const lot = match?.lots[selected];
  const owner = lot ? match?.players[lot.owner] : undefined;
  return (
    <foreignObject x="225" y="225" width="550" height="550">
      <div className="dala-board-center">
        <span className="dala-board-center-eyebrow">
          ДАЛА ДӘУЛЕТІ · {board.name}
        </span>
        <div className="dala-board-center-turn">
          <span style={{ background: player?.color ?? "#456e5a" }}>
            {player?.name.slice(0, 1) ?? "✦"}
          </span>
          <div>
            <h2>{player ? `${player.name} · жүріс` : "Өз жолыңды таңда"}</h2>
            <p>
              {match
                ? PHASE_LABELS[match.phase]
                : "Кәсіпті таңдап, қаланы зертте"}
            </p>
          </div>
        </div>
        {match && (
          <div className="dala-board-center-stats">
            <div>
              <small>Айналым</small>
              <b>{match.round}</b>
            </div>
            <div>
              <small>Қаражат</small>
              <b>{money(player?.cash ?? 0)}</b>
            </div>
          </div>
        )}
        <div className="dala-board-center-property">
          <span className="dala-board-center-eyebrow">
            {tile
              ? tile.landmark
                ? "ҚАЛА НЫСАНЫ"
                : tile.street
                  ? "ҚАЛА КӨШЕСІ"
                  : "ТАҢДАЛҒАН КӘСІП"
              : "КІШКЕНТАЙ ҚАДАМ · ҮЛКЕН МҮМКІНДІК"}
          </span>
          <h3>{tile?.name ?? "Қала сенен басталады"}</h3>
          <p>
            {tile
              ? `${owner?.name ?? "Банк"}${lot ? ` · ${lot.level} ғимарат` : ""}`
              : "Алаңдағы ғимаратты басып, бағасы мен жалдау ақысын көр."}
          </p>
          {tile && (
            <>
              <strong style={{ color: tile.color }}>
                {money(tile.price || tile.amount)}
              </strong>
              <button onClick={onInspect}>Толық мәлімет ↗</button>
            </>
          )}
        </div>
        <div className="dala-board-center-hint">
          ✦ Түсті топты жина · Кәсіпті дамыт · Табыс тап
        </div>
      </div>
    </foreignObject>
  );
}
