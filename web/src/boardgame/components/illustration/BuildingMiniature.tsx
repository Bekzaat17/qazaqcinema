import type { Board, Tile } from "../../types";
import { Tree } from "./Scenery";

function StreetMiniature() {
  return (
    <g className="dala-building-miniature" pointerEvents="none">
      <path
        d="m-46-15 65-30 30 29-65 31Z"
        fill="#486052"
        transform="translate(0 7)"
        opacity=".25"
      />
      <path d="m-46-15 65-30 30 29v8l-65 31-30-29Z" fill="#ac9f7d" />
      <path d="m-46-15 65-30 30 29-65 31Z" fill="#d7d4b9" />
      <path d="m-37-6 65-30 13 12-65 31Z" fill="#8b9690" />
      <path
        d="m-30 0 64-30"
        stroke="#f4e7bf"
        strokeWidth="2"
        strokeDasharray="7 6"
      />
      <path d="m-44-14 65-29M-19 14 65-30" stroke="#f0e6c8" strokeWidth="2" />
      <Tree x={-27} y={-22} scale={0.56} />
      <Tree x={20} y={9} scale={0.5} />
      <path
        d="M-4-17v-27m-5 0h10"
        fill="none"
        stroke="#50665c"
        strokeWidth="2"
      />
      <ellipse cx="-4" cy="-44" rx="5" ry="3" fill="#f4da91" stroke="#a3915a" />
      <path d="M36-3v-27m-4 0h8" stroke="#50665c" strokeWidth="2" />
      <circle cx="36" cy="-31" r="3" fill="#f4da91" />
    </g>
  );
}

export default function BuildingMiniature({
  board,
  tile,
  level,
}: {
  board: Board;
  tile: Tile;
  level: number;
}) {
  if (tile.kind !== "property" && tile.kind !== "station") {
    const symbol =
      tile.kind === "start"
        ? "✦"
        : tile.kind === "chance"
          ? "?"
          : tile.kind === "tax"
            ? "₸"
            : "❋";
    return (
      <g className="dala-miniature-special" pointerEvents="none">
        <ellipse cy="0" rx="30" ry="15" fill="#a99159" opacity=".25" />
        <ellipse
          cy="-9"
          rx="29"
          ry="22"
          fill="#d7b86d"
          stroke="#f9e6aa"
          strokeWidth="3"
        />
        <text
          y="1"
          textAnchor="middle"
          fontSize="30"
          fontFamily="Georgia"
          fill="#fff4c9"
        >
          {symbol}
        </text>
      </g>
    );
  }
  const landmarkSprite = tile.sprite ?? -1;
  const sprite =
    landmarkSprite >= 0 ? landmarkSprite : (tile.street_sprite ?? -1);
  const atlas =
    landmarkSprite >= 0 ? board.miniature_atlas : board.street_atlas;
  if (sprite < 0 || !atlas) return <StreetMiniature />;
  return (
    <g className="dala-building-miniature" pointerEvents="none">
      <ellipse cy="16" rx="43" ry="12" fill="#365143" opacity=".23" />
      <svg
        x="-55"
        y="-68"
        width="110"
        height="100"
        viewBox={`${(sprite % 4) * 100} ${Math.floor(sprite / 4) * 100} 100 100`}
        overflow="hidden"
      >
        <image
          href={atlas}
          width="400"
          height="200"
          preserveAspectRatio="none"
        />
      </svg>
      {level > 0 && (
        <g transform="translate(31 -40)">
          <circle r="13" fill="#316551" stroke="#f3d590" strokeWidth="2" />
          <text y="4" textAnchor="middle" fontSize="12" fill="#fff0bf">
            {level === 4 ? "★" : level}
          </text>
        </g>
      )}
    </g>
  );
}
