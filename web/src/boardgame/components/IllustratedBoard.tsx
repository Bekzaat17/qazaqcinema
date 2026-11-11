import { memo } from "react";
import type { Board, Match } from "../types";
import type { PlayerAppearance } from "../../ui-kit/PlayerAvatar";
import { illustratedPoint } from "../layout";
import { money, moneyLabel } from "../format";
import BuildingMiniature from "./illustration/BuildingMiniature";
import PawnLayer from "./PawnLayer";
import CityLife from "./CityLife";
export { illustratedPoint } from "../layout";

function lines(name: string) {
  const result: string[] = [];
  let current = "";
  for (const word of name.split(" ")) {
    if (current && `${current} ${word}`.length > 15) {
      result.push(current); current = word;
    } else current = current ? `${current} ${word}` : word;
  }
  if (current) result.push(current);
  return result.slice(0, 2);
}

function FlatCell({ board, match, index, selected, onSelect }:
  { board: Board; match: Match | null; index: number; selected: boolean;
    onSelect: (index: number) => void }) {
  const tile = board.tiles[index];
  const lot = match?.lots[index];
  const owner = lot && match ? match.players[lot.owner] : null;
  const active = match?.players[match.turn]?.position === index;
  const point = illustratedPoint(index, board.tiles.length, true);
  const size = 720 / (board.tiles.length / 4);
  const scale = size / 120;
  const color = lot?.mortgaged ? "#a9ac9d" : owner?.color ?? tile.color;
  return <g transform={`translate(${point.x} ${point.y})`} className="dala-flat-cell"
    >
    <title>{`${index + 1}. ${tile.name}`}</title>
    <g transform={`scale(${scale})`}>
      <rect
    role="button" tabIndex={0} aria-current={active ? "location" : undefined}
    aria-label={`№ ${index + 1}. ${tile.name}${tile.price ? `, ${moneyLabel(tile.price)}` : ""}${owner ? `, ${owner.name}` : ""}`}
    onClick={() => onSelect(index)} onKeyDown={(event) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(index); }
    }}

        className="dala-cell-ground" x="-59" y="-59" width="118" height="118" rx="7"
        fill={index === 0 ? "#e7ecd4" : "#fff9ed"}
        stroke={selected ? "#af7c25" : active ? "#c89937" : "#b4ac98"}
        strokeWidth={selected || active ? 3 : 1.3} />
      <g pointerEvents="none">
      <path d="M-51-57H51Q57-57 57-51v3H-57v-3Q-57-57-51-57Z" fill={tile.kind === "property" ? tile.color : "#b6b2a1"} opacity={lot?.mortgaged ? .5 : 1} />
      <circle cx="-43" cy="-34" r="9" fill={owner ? color : "#eee8d7"} />
      <text x="-43" y="-31" textAnchor="middle" fontSize="9" fontWeight="800"
        fill={owner ? "#fff" : "#6e674e"}>{index + 1}</text>
      <g transform="translate(1 -7) scale(.76)" pointerEvents="none">
        <BuildingMiniature board={board} tile={tile} level={lot?.level ?? 0} />
      </g>
      {lines(tile.name).map((line, i) => <text key={i} x="0" y={25 + i * 12}
        textAnchor="middle" fontSize="11.5" fontWeight="650" fill="#34483d">{line}</text>)}
      <text x="0" y="51" textAnchor="middle" fontSize="10.5" fontWeight="600" fill="#82602d">
        {tile.price ? money(tile.price) : tile.amount ? `${tile.kind === "rest" ? "+" : ""}${money(tile.amount)}` : index === 0 ? "← БАСТАУ" : ""}
      </text>
      {lot?.mortgaged && <path d="m-48-44 96 88" stroke="#85887b" strokeWidth="2" opacity=".7" />}
      </g>
    </g>
  </g>;
}

function TrafficLight({ x, y, rotate = 0 }: { x: number; y: number; rotate?: number }) {
  return <g transform={`translate(${x} ${y}) rotate(${rotate})`}>
    <path d="M0 6v12" stroke="#46544b" strokeWidth="3" />
    <rect x="-4" y="-10" width="8" height="19" rx="2.5" fill="#263e35" stroke="#f4e6b9" strokeWidth=".8" />
    <circle className="dala-signal-red" cy="-5" r="2" fill="#db6551" /><circle className="dala-signal-yellow" cy="0" r="2" fill="#e9bd49" />
    <circle className="dala-signal-green" cy="5" r="2" fill="#90c784" />
  </g>;
}

function IllustratedBoard({ board, match, appearances, selected, onSelect, onAnimate,
  zoom = 1, rotation = 0 }:
  { board: Board; match: Match | null; appearances?: Record<string, PlayerAppearance>;
    selected: number; onSelect: (index: number) => void; onAnimate: (active: boolean) => void;
    zoom?: number; rotation?: number }) {
  return <svg className="dala-illustrated-board dala-flat-board" viewBox="45 45 910 910"
    role="group" aria-label="QazaqPlay. Нөмірленген ұяшықтары бар қала картасы. Кәсіпті басып аш."
    style={{ transform: `scale(${zoom}) rotate(${rotation}deg)` }}>
    <g aria-hidden="true" pointerEvents="none">
      <rect x="72" y="72" width="856" height="856" rx="18" fill="#d5dfca" />
      <image href={board.biome === "turkistan" ? "/boardgame/art/turkistan-map-v2.webp" : "/boardgame/art/almaty-map-v2.webp"} x="200" y="200" width="600" height="600" preserveAspectRatio="xMidYMid slice" />
      <CityLife biome={board.biome} />
      <rect x="204" y="204" width="592" height="592" rx="16" fill="none" stroke="#f6eacd" strokeWidth="4" />
      {[[220, 220, 0], [780, 220, 90], [780, 780, 180], [220, 780, 270]].map(([x, y, r]) =>
        <TrafficLight key={`${x}-${y}`} x={x} y={y} rotate={r} />)}
    </g>
    {board.tiles.map((_, index) => <FlatCell key={board.tiles[index].id} board={board} match={match}
      index={index} selected={selected === index} onSelect={onSelect} />)}
    <g aria-hidden="true" pointerEvents="none">
      {board.tiles.map((_, index) => {
        if (index % 3 !== 1) return null;
        const a = illustratedPoint(index, board.tiles.length, true);
        const b = illustratedPoint(index + 1, board.tiles.length, true);
        const angle = Math.atan2(b.y - a.y, b.x - a.x) * 180 / Math.PI;
        return <g key={index} transform={`translate(${(a.x + b.x) / 2} ${(a.y + b.y) / 2}) rotate(${angle})`}>
          <circle r="10" fill="#efe5c5" stroke="#c6b58d" />
          <path d="m-3-4 5 4-5 4M2 0H-5" fill="none" stroke="#8a682c" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </g>;
      })}
    </g>
    <PawnLayer match={match} count={board.tiles.length} painted={true} appearances={appearances} onAnimate={onAnimate} />
  </svg>;
}
export default memo(IllustratedBoard);
