import { memo, useEffect, useId, useRef, useState } from "react";
import type { Board, Lot, Match, Move } from "../types";
import Town, { Building, Yurt } from "./illustration/Scenery";
import MapGarden from "./illustration/MapGarden";
import ArtworkHotspot from "./illustration/ArtworkHotspot";

type Point = { x: number; y: number };
export function illustratedPoint(
  index: number,
  count: number,
  painted = false,
): Point {
  const side = count / 4,
    step = 600 / side,
    half = 300;
  let x: number, z: number;
  if (index <= side) {
    x = half - index * step;
    z = half;
  } else if (index <= side * 2) {
    x = -half;
    z = half - (index - side) * step;
  } else if (index <= side * 3) {
    x = -half + (index - side * 2) * step;
    z = -half;
  } else {
    x = half;
    z = -half + (index - side * 3) * step;
  }
  const point = { x: 500 + (x - z) * 0.7, y: 420 + (x + z) * 0.36 };
  return painted
    ? { x: 500 + x * 1.032 + z * 0.3, y: 445 - x * 0.12 + z * 0.648 }
    : point;
}
function words(text: string): string[] {
  const parts = text.split(" "),
    result: string[] = [];
  let line = "";
  for (const word of parts) {
    if ((line + " " + word).trim().length > 13 && line) {
      result.push(line);
      line = word;
    } else line = (line + " " + word).trim();
  }
  if (line) result.push(line);
  return result.slice(0, 3);
}
function PropertyTile({
  board,
  index,
  lot,
  ownerColor,
  selected,
  onSelect,
  shadow,
  glow,
  onHover,
}: {
  board: Board;
  index: number;
  lot: Lot | undefined;
  ownerColor: string | undefined;
  selected: boolean;
  onSelect: (index: number) => void;
  shadow: string;
  glow: string;
  onHover: (index: number) => void;
}) {
  const point = illustratedPoint(
      index,
      board.tiles.length,
      !!board.illustration,
    ),
    tile = board.tiles[index],
    factor = 24 / board.tiles.length,
    labels = words(tile.name),
    color = lot?.mortgaged ? "#a4a998" : (ownerColor ?? tile.color);
  if (board.illustration)
    return (
      <ArtworkHotspot
        board={board}
        index={index}
        point={point}
        lot={lot}
        color={color}
        selected={selected}
        onSelect={onSelect}
        onHover={onHover}
      />
    );
  return (
    <g
      transform={`translate(${point.x} ${point.y})`}
      className={`dala-svg-tile ${selected ? "selected" : ""}`}
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
      style={{ "--tile-glow": color } as React.CSSProperties}
    >
      <title>{tile.name}</title>
      <g className="dala-svg-tile-rise" style={{ transformOrigin: "center" }}>
        <g transform={`scale(${factor})`}>
          <path
            d="m-65 0 65 34 65-34v9L0 43-65 9Z"
            fill="#c4b18a"
            stroke="#ae9c78"
            strokeWidth=".6"
          />
          <path
            d="M0-34 65 0 0 34-65 0Z"
            fill="#fff7df"
            stroke={selected ? color : "#dacaa1"}
            strokeWidth={selected ? 2.5 : 1}
            filter={`url(#${shadow})`}
          />
          <path
            d="M-65 0 0-34 65 0 51 7 0-20-51 7Z"
            fill={tile.color}
            opacity={lot?.mortgaged ? 0.5 : 0.9}
          />
          {selected && (
            <path
              className="dala-svg-selected-ring"
              d="M0-35 67 0 0 35-67 0Z"
              stroke={color}
              strokeWidth="2"
              fill="none"
              filter={`url(#${glow})`}
            />
          )}
          {["property", "station"].includes(tile.kind) ? (
            <>
              <g transform="translate(16 -23) scale(.42)">
                {tile.kind === "station" ? (
                  <g>
                    <path d="m-25-5 22-8 25 12v15L0 22-25 10Z" fill="#729995" />
                    <path d="M-20-2 0 7 0 15-20 6Z" fill="#bad3c4" />
                    <circle cx="-14" cy="13" r="4" fill="#5b736b" />
                    <circle cx="9" cy="20" r="4" fill="#5b736b" />
                  </g>
                ) : board.biome === "steppe" ? (
                  <Yurt scale={0.9} color={tile.color} />
                ) : (
                  <Building
                    scale={lot?.level === 4 ? 0.8 : 0.6}
                    color={tile.color}
                    hotel={lot?.level === 4}
                  />
                )}
              </g>
              {labels.map((line, i) => (
                <text
                  key={i}
                  x="0"
                  y={labels.length > 2 ? -2 + i * 9 : 8 + i * 11}
                  textAnchor="middle"
                  fontSize={labels.length > 2 ? 9.5 : 10.8}
                  fontWeight="550"
                  fill="#455e50"
                >
                  {line}
                </text>
              ))}
            </>
          ) : (
            <>
              <text
                y="-4"
                textAnchor="middle"
                fill={tile.kind === "chance" ? "#c3a064" : "#718e71"}
                fontSize="23"
                fontFamily="Georgia"
              >
                {tile.kind === "chance"
                  ? "?"
                  : tile.kind === "start"
                    ? "➜"
                    : tile.kind === "rest"
                      ? "✿"
                      : "₸"}
              </text>
              <text y="12" textAnchor="middle" fontSize="10" fill="#6b7c5e">
                {tile.name}
              </text>
            </>
          )}
          <text
            y="29"
            textAnchor="middle"
            fontSize="9"
            fontWeight="650"
            fill="#a58b54"
          >
            {tile.price
              ? `${tile.price} ₸`
              : tile.kind === "rest"
                ? `+${tile.amount} ₸`
                : tile.kind === "tax"
                  ? `${tile.amount} ₸`
                  : ""}
          </text>
          {lot && (
            <>
              <path
                d="m-32 27 32 16 32-16"
                stroke={color}
                strokeWidth="4"
                fill="none"
              />
              {lot.level > 0 && (
                <g transform="translate(-34 -2)">
                  <circle r="9" fill={color} />
                  <text
                    y="3.5"
                    textAnchor="middle"
                    fill="#fff8e2"
                    fontSize="9"
                    fontWeight="700"
                  >
                    {lot.level === 4 ? "★" : lot.level}
                  </text>
                </g>
              )}
            </>
          )}
        </g>
      </g>
    </g>
  );
}
function PawnLayer({
  match,
  count,
  painted,
  onAnimate,
}: {
  match: Match | null;
  count: number;
  painted: boolean;
  onAnimate: (active: boolean) => void;
}) {
  const [positions, setPositions] = useState<Point[]>([]),
    previous = useRef<Move[]>([]),
    initial = useRef("");
  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  useEffect(() => {
    const moves = match?.moves ?? [],
      key = match?.players.map((p) => p.id).join(":") ?? "";
    if (!match) {
      setPositions([]);
      previous.current = [];
      initial.current = "";
      onAnimate(false);
      return;
    }
    const final = match.players.map((p) =>
      illustratedPoint(p.position, count, painted),
    );
    if (key !== initial.current || reduced) {
      initial.current = key;
      previous.current = structuredClone(moves);
      setPositions(final);
      onAnimate(false);
      return;
    }
    let overlap = 0;
    for (let n = Math.min(previous.current.length, moves.length); n > 0; n--)
      if (
        JSON.stringify(previous.current.slice(-n)) ===
        JSON.stringify(moves.slice(0, n))
      ) {
        overlap = n;
        break;
      }
    const fresh =
      JSON.stringify(previous.current) === JSON.stringify(moves)
        ? []
        : moves.slice(overlap);
    previous.current = structuredClone(moves);
    if (!fresh.length) {
      setPositions(final);
      onAnimate(false);
      return;
    }
    let frame = 0,
      last = 0,
      elapsed = 0,
      moveIndex = 0;
    const current = match.players.map((p) =>
      illustratedPoint(p.position, count, painted),
    );
    fresh.forEach((move) => {
      current[move.player] = illustratedPoint(move.start, count, painted);
    });
    onAnimate(true);
    const tick = (time: number) => {
      if (document.hidden) {
        setPositions(final);
        onAnimate(false);
        return;
      }
      elapsed += last ? Math.min(time - last, 100) : 0;
      last = time;
      const move = fresh[moveIndex];
      const step = Math.floor(elapsed / 100),
        t = (elapsed % 100) / 100;
      if (step >= move.steps) {
        current[move.player] = illustratedPoint(move.end, count, painted);
        moveIndex++;
        elapsed = 0;
        if (moveIndex >= fresh.length) {
          setPositions(final);
          onAnimate(false);
          return;
        }
      } else {
        const a = illustratedPoint((move.start + step) % count, count, painted),
          b = illustratedPoint((move.start + step + 1) % count, count, painted);
        current[move.player] = {
          x: a.x + (b.x - a.x) * t,
          y: a.y + (b.y - a.y) * t - Math.sin(t * Math.PI) * 10,
        };
      }
      setPositions([...current]);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(frame);
    };
  }, [match, count, onAnimate, reduced, painted]);
  return (
    <g className="dala-svg-pawns" aria-hidden="true">
      {match?.players.map((player, i) => {
        if (player.bankrupt) return null;
        const point =
          positions[i] ?? illustratedPoint(player.position, count, painted);
        return (
          <g
            key={player.id}
            transform={`translate(${point.x + (i % 2 ? 10 : -10)} ${point.y + (i < 2 ? -7 : 8)})`}
          >
            <ellipse cy="7" rx="12" ry="5" fill="#47685c" opacity=".2" />
            <path
              d="M-9-7-11 8Q0 17 11 8L9-7"
              fill={player.color}
              stroke="#fff7db"
              strokeWidth="1.5"
            />
            <ellipse
              cy="-9"
              rx="7"
              ry="8"
              fill="#edcca0"
              stroke="#fff6df"
              strokeWidth="1"
            />
            <path
              d="M-10-12 0-31 10-12Q0-5-10-12"
              fill={player.color}
              stroke="#fff1ce"
              strokeWidth="1"
            />
            <path d="m0-30-3-6 3-3 3 3Z" fill="#e7bf68" />
          </g>
        );
      })}
    </g>
  );
}
function IllustratedBoard({
  board,
  match,
  selected,
  onSelect,
  onAnimate,
  zoom = 1,
  rotation = 0,
}: {
  board: Board;
  match: Match | null;
  selected: number;
  onSelect: (index: number) => void;
  onAnimate: (active: boolean) => void;
  zoom?: number;
  rotation?: number;
}) {
  const [hovered, setHovered] = useState(-1);
  const id = useId().replace(/:/g, ""),
    shadow = `shadow-${id}`,
    glow = `glow-${id}`;
  return (
    <svg
      className={`dala-illustrated-board ${board.miniature_atlas ? "dala-object-map" : ""}`}
      viewBox={board.illustration ? "-60 100 1120 800" : "0 80 1000 730"}
      role="group"
      aria-label="Қазақша ойын әлемі. Кәсіп ұяшығын басып ашыңыз."
      style={{ transform: `scale(${zoom}) rotate(${rotation}deg)` }}
    >
      <defs>
        <radialGradient id={`grass-${id}`}>
          <stop stopColor="#cad8b6" />
          <stop offset="1" stopColor="#8fa97a" />
        </radialGradient>
        <filter id={shadow} x="-30%" y="-50%" width="160%" height="220%">
          <feDropShadow
            dx="0"
            dy="3"
            stdDeviation="2"
            floodColor="#766e49"
            floodOpacity=".12"
          />
        </filter>
        <filter id={glow} x="-50%" y="-90%" width="200%" height="280%">
          <feGaussianBlur stdDeviation="3" />
        </filter>
        <linearGradient id={`soil-${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop stopColor="#baa77b" />
          <stop offset="1" stopColor="#8d8765" />
        </linearGradient>
      </defs>
      {!board.illustration && (
        <g className="dala-island-shadow" aria-hidden="true">
          <ellipse
            cx="500"
            cy="718"
            rx="340"
            ry="28"
            fill="#688d80"
            opacity=".11"
          />
          <path
            d="m10 421 490 253 490-253v28L500 714 10 449Z"
            fill={`url(#soil-${id})`}
          />
          <path d="m10 421 490 253 490-253v8L500 683 10 429Z" fill="#e0c98c" />
          <path
            d="m385 654 40 52 36-13 39 35 43-30 53-1 29-43"
            fill="#939275"
            opacity=".6"
          />
        </g>
      )}
      {board.illustration ? (
        <g className="dala-map-base" aria-hidden="true">
          <ellipse
            cx="520"
            cy="704"
            rx="430"
            ry="48"
            fill="#618b73"
            opacity=".14"
          />
          <path
            d="M18 254 235 723 982 636v30L235 753 18 284Z"
            fill="#ba9d68"
            stroke="#ac915d"
            strokeWidth="2"
          />
          <path d="m235 723 747-87v30l-747 87Z" fill="#d5bc86" />
          <g transform="matrix(.86 -.1 .25 .54 -55 225)">
            <rect
              x="66"
              y="66"
              width="868"
              height="868"
              rx="30"
              fill={`url(#grass-${id})`}
              stroke="#8c8056"
              strokeWidth="5"
            />
            <rect
              x="82"
              y="82"
              width="836"
              height="836"
              rx="22"
              fill="none"
              stroke="#d9be82"
              strokeWidth="2"
            />
            <rect
              x="210"
              y="210"
              width="580"
              height="580"
              rx="18"
              fill="#cddfc8"
              stroke="#c1ac73"
              strokeWidth="2"
            />
            <rect
              x="140"
              y="140"
              width="720"
              height="720"
              rx="20"
              fill="none"
              stroke="#8d9d75"
              strokeWidth="112"
              opacity=".6"
            />
            <rect
              x="140"
              y="140"
              width="720"
              height="720"
              rx="20"
              fill="none"
              stroke="#d7c89f"
              strokeWidth="98"
            />
            <rect
              x="140"
              y="140"
              width="720"
              height="720"
              rx="20"
              fill="none"
              stroke="#eee0b8"
              strokeWidth="2"
              strokeDasharray="4 12"
            />
          </g>
        </g>
      ) : (
        <Town board={board} />
      )}
      {board.illustration && <MapGarden board={board} />}
      <g>
        {board.tiles
          .map((_, index) => index)
          .sort(
            (a, b) =>
              Number(a === hovered) - Number(b === hovered) ||
              illustratedPoint(a, board.tiles.length, !!board.illustration).y -
                illustratedPoint(b, board.tiles.length, !!board.illustration).y,
          )
          .map((index) => (
            <PropertyTile
              key={board.tiles[index].id}
              board={board}
              index={index}
              lot={match?.lots[index]}
              ownerColor={
                match?.lots[index]
                  ? match.players[match.lots[index].owner].color
                  : undefined
              }
              selected={selected === index}
              onSelect={onSelect}
              shadow={shadow}
              glow={glow}
              onHover={setHovered}
            />
          ))}
      </g>
      <PawnLayer
        match={match}
        count={board.tiles.length}
        painted={!!board.illustration}
        onAnimate={onAnimate}
      />
    </svg>
  );
}

export default memo(IllustratedBoard);
