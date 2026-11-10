import { useId, type CSSProperties } from "react";
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
    factor = 24 / board.tiles.length,
    crop = useId().replace(/:/g, "");
  return (
    <g
      transform={`translate(${point.x} ${point.y})`}
      className={`dala-svg-tile dala-artwork-hotspot ${selected ? "selected" : ""}`}
      role="button"
      tabIndex={0}
      aria-label={`${tile.name}${tile.price ? `, ${tile.price} теңге` : ""}${lot ? `, ${lot.level} ғимарат` : ""}`}
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
      <defs>
        <clipPath id={crop}>
          <path d="M0-38 65-3 0 32-65-3Z" />
        </clipPath>
      </defs>
      <g className="dala-svg-tile-rise" style={{ transformOrigin: "center" }}>
        <g transform={`scale(${factor})`}>
          <path
            className="dala-hotspot-hit"
            d="M0-42 69-3 0 36-69-3Z"
            fill="transparent"
            stroke="none"
          />
          <g className="dala-hotspot-fragment" clipPath={`url(#${crop})`}>
            <image
              href={board.illustration}
              x={(40 - point.x) / factor}
              y={(60 - point.y) / factor}
              width={920 / factor}
              height={650 / factor}
              preserveAspectRatio="xMidYMid meet"
              pointerEvents="none"
            />
          </g>
          <path
            className="dala-hotspot-outline"
            d="M0-38 65-3 0 32-65-3Z"
            fill={color}
            fillOpacity=".1"
            stroke={color}
            strokeWidth="2"
          />
          <g className="dala-hotspot-marker">
            <circle
              cy="4"
              r={lot ? 12 : 9}
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
              {lot?.level ? (lot.level === 4 ? "★" : lot.level) : index + 1}
            </text>
            {lot?.mortgaged && (
              <path d="m-7-4 14 14" stroke="#8e957b" strokeWidth="2" />
            )}
          </g>
          <g className="dala-hotspot-label">
            <rect
              x="-77"
              y="28"
              width="154"
              height={tile.price ? 41 : 27}
              rx="8"
              fill="#244b43"
              fillOpacity=".95"
              stroke="#e4c47e"
              strokeWidth="1"
            />
            <text
              y="44"
              textAnchor="middle"
              fontSize="10.5"
              fontWeight="600"
              fill="#fff7d9"
            >
              {tile.name}
            </text>
            {tile.price > 0 && (
              <text y="59" textAnchor="middle" fontSize="9" fill="#e6cd8c">
                {tile.price} ₸
              </text>
            )}
          </g>
        </g>
      </g>
    </g>
  );
}
