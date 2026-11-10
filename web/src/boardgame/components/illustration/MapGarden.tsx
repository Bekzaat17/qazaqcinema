import type { Board } from "../../types";

function Quarter({
  atlas,
  sprite,
  x,
  y,
}: {
  atlas: string;
  sprite: number;
  x: number;
  y: number;
}) {
  return (
    <svg
      x={x}
      y={y}
      width="165"
      height="140"
      viewBox={`${(sprite % 4) * 100} ${Math.floor(sprite / 4) * 100} 100 100`}
      overflow="hidden"
    >
      <image href={atlas} width="400" height="200" preserveAspectRatio="none" />
    </svg>
  );
}

export default function MapGarden({ board }: { board: Board }) {
  const first = board.biome === "turkistan" ? 4 : 0;
  return (
    <g aria-hidden="true" pointerEvents="none">
      <g transform="matrix(.86 -.1 .25 .54 -55 225)">
        <path
          d="M270 330Q500 260 735 355M290 690Q500 710 720 650M440 290Q370 500 420 710"
          fill="none"
          stroke="#d9c79a"
          strokeWidth="30"
          strokeLinecap="round"
        />
        <path
          d="M270 330Q500 260 735 355M290 690Q500 710 720 650M440 290Q370 500 420 710"
          fill="none"
          stroke="#efe0b8"
          strokeWidth="21"
          strokeLinecap="round"
        />
        <ellipse cx="585" cy="520" rx="110" ry="145" fill="#e4dab4" />
        <ellipse cx="585" cy="520" rx="97" ry="131" fill="#88c1b8" />
        <ellipse cx="585" cy="520" rx="81" ry="112" fill="#abd7c7" />
        <path
          d="M530 480q55-25 110 0m-120 48q60-25 120 0m-100 40q45-18 90 0"
          fill="none"
          stroke="#e3f1d8"
          strokeWidth="4"
          opacity=".8"
        />
        <ellipse cx="342" cy="580" rx="35" ry="65" fill="#b6c991" />
        <ellipse cx="685" cy="340" rx="40" ry="30" fill="#b6c991" />
      </g>
      {board.street_atlas && (
        <>
          <Quarter atlas={board.street_atlas} sprite={first} x={300} y={323} />
          <Quarter
            atlas={board.street_atlas}
            sprite={first + 2}
            x={487}
            y={260}
          />
          <Quarter
            atlas={board.street_atlas}
            sprite={first + 3}
            x={583}
            y={446}
          />
        </>
      )}
    </g>
  );
}
