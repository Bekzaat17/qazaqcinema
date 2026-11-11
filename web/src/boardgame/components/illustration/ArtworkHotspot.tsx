import { cellCorners } from "../../layout";
import { money, moneyLabel } from "../../format";
import { type CSSProperties } from "react";
import BuildingMiniature from "./BuildingMiniature";
import type { Board, Lot } from "../../types";

export default function ArtworkHotspot({
  board,
  index,
  point,
  lot,
  color,
  selected,
  onSelect,
  onHover,
}: {
  board: Board;
  index: number;
  point: { x: number; y: number };
  lot: Lot | undefined;
  color: string;
  selected: boolean;
  onSelect: (index: number) => void;
  onHover: (index: number) => void;
}) {
  const tile = board.tiles[index],
    factor = 24 / board.tiles.length;
  return (
    <g
      transform={`translate(${point.x} ${point.y})`}
      className={`dala-svg-tile dala-artwork-hotspot dala-square-tile ${selected ? "selected" : ""}`}
      role="button"
      tabIndex={0}
      aria-label={`№ ${index + 1}. ${tile.name}${tile.price ? `, ${moneyLabel(tile.price)}` : ""}${lot ? `, ${lot.level} ғимарат` : ""}`}
      onClick={() => onSelect(index)}
      onPointerEnter={() => onHover(index)}
      onPointerLeave={() => onHover(-1)}
      onFocus={() => onHover(index)}
      onBlur={() => onHover(-1)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect(index);
        }
      }}
      style={{ "--tile-glow": color } as CSSProperties}
    >
      <title>{tile.name}</title>
      <polygon className="dala-hotspot-hit" fill="transparent"
        points={cellCorners(index, board.tiles.length)
          .map((p) => `${p.x - point.x},${p.y - point.y}`).join(" ")} />
      <g className="dala-svg-tile-rise" style={{ transformOrigin: "center" }}>
        <g transform={`scale(${factor})`}>
          <ellipse
            className="dala-object-selection"
            cy="8"
            rx="52"
            ry="27"
            fill={color}
            stroke={color}
            strokeWidth="2"
          />
          <g transform="translate(0 -7) scale(.8)"><BuildingMiniature
            board={board}
            tile={tile}
            level={lot?.level ?? 0}
          /></g>
          <g className="dala-hotspot-marker" transform="translate(-38 -24)">
            <circle
              cy="4"
              r={lot ? 10 : 8}
              fill={lot ? color : "#fff3d7"}
              stroke={lot ? "#fff0c5" : "#c3a369"}
              strokeWidth="2"
            />
            <text
              y="7.5"
              textAnchor="middle"
              fill={lot ? "#fff7df" : "#a38955"}
              fontSize="9"
              fontWeight="700"
            >
              {index + 1}
            </text>
            {lot?.mortgaged && (
              <path d="m-7-4 14 14" stroke="#8e957b" strokeWidth="2" />
            )}
          </g>
          <g className="dala-square-tile-label" pointerEvents="none">
            <text
              y="27"
              textAnchor="middle"
              fontSize="10"
              textLength={tile.name.length > 17 ? 100 : undefined}
              lengthAdjust="spacingAndGlyphs"
              fontWeight="600"
              fill="#31564c"
            >
              {tile.name}
            </text>
            {tile.price > 0 && (
              <text y="40" textAnchor="middle" fontSize="9" fill="#8a6d36">
                {money(tile.price)}
              </text>
            )}
          </g>
        </g>
      </g>
    </g>
  );
}
