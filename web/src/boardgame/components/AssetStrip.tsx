import type { Board, Match } from "../types";
import BuildingMiniature from "./illustration/BuildingMiniature";

export default function AssetStrip({ board, match, me, onSelect }:
  { board: Board; match: Match; me: number; onSelect: (index: number) => void }) {
  const assets = board.tiles.flatMap((tile, i) => match.lots[i]?.owner === me ? [{ tile, index: i, lot: match.lots[i] }] : []);
  return <section className="dala-assets-strip" aria-label="Менің мүлкім">
    <div className="dala-assets-title"><b>Менің мүлкім</b><span>{assets.length} нысан · басқару үшін бас</span></div>
    <div className="dala-assets-row">
      {assets.length ? assets.map(({ tile, index, lot }) => <button key={tile.id}
        className={lot.mortgaged ? "is-mortgaged" : ""} style={{ borderTopColor: tile.color }}
        onClick={() => onSelect(index)} aria-label={`${tile.name}: ${lot.mortgaged ? "кепілде" : lot.level ? `${lot.level} құрылыс` : "сенің мүлкің"}`}>
        <svg viewBox="-66 -76 132 124" width="44" height="44" aria-hidden="true"><BuildingMiniature board={board} tile={tile} level={lot.level} /></svg>
        <span><b>{tile.name}</b><small>{lot.mortgaged ? "Кепілде" : lot.level === tile.rents.length - 1 ? "Қонақүй" : lot.level ? `${lot.level} үй` : tile.kind === "property" ? "Топты жина" : "Сенің бекетің"}</small></span>
      </button>) : <p>Әзірге мүлік жоқ. Сатып алған кәсіптерің осында көрінеді.</p>}
    </div>
  </section>;
}
