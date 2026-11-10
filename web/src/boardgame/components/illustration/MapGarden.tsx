import type { Board } from "../../types";
import ParkDecoration, { type ParkPlacement } from "./ParkDecoration";

const DECORATIONS: readonly ParkPlacement[] = [
  { kind: "lawn", x: 375, y: 400, size: 145 },
  { kind: "lawn", x: 470, y: 555, size: 135 },
  { kind: "lawn", x: 665, y: 365, size: 105 },
  { kind: "tree", x: 343, y: 420, size: 125 },
  { kind: "apple", x: 432, y: 366, size: 106 },
  { kind: "spruce", x: 685, y: 402, size: 110 },
  { kind: "tree", x: 402, y: 537, size: 110 },
  { kind: "apple", x: 696, y: 541, size: 100 },
  { kind: "flowers", x: 370, y: 469, size: 90 },
  { kind: "flowers", x: 616, y: 563, size: 100 },
  { kind: "flowers", x: 640, y: 337, size: 85 },
  { kind: "bench", x: 462, y: 454, size: 85 },
  { kind: "bench", x: 531, y: 558, size: 85 },
  { kind: "bench", x: 682, y: 462, size: 80 },
  { kind: "lamp", x: 483, y: 406, size: 92 },
  { kind: "lamp", x: 460, y: 540, size: 90 },
  { kind: "lamp", x: 666, y: 502, size: 90 },
  { kind: "fountain", x: 577, y: 465, size: 105 },
];

export default function MapGarden({ board }: { board: Board }) {
  const warm = board.biome === "turkistan";
  return (
    <g aria-hidden="true" pointerEvents="none" className="dala-park">
      <g transform="matrix(.86 -.1 .25 .54 -55 225)">
        <path
          d="M260 350Q330 265 470 310L455 450Q315 485 260 350Z"
          fill={warm ? "#b9cc89" : "#a8c58b"}
        />
        <path
          d="M310 610Q385 530 475 605L540 705Q345 725 310 610Z"
          fill="#a8c688"
        />
        <path d="M650 280Q760 285 740 410L640 400Z" fill="#b7cd91" />
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
        <ellipse
          className="dala-park-ripple"
          cx="585"
          cy="520"
          rx="40"
          ry="54"
          fill="none"
          stroke="#f6ffe9"
          strokeWidth="3"
        />
      </g>
      {DECORATIONS.filter((item) => item.kind === "lawn").map((item, index) => (
        <ParkDecoration key={`lawn-${index}`} {...item} />
      ))}
      {DECORATIONS.filter((item) => item.kind !== "lawn")
        .sort((a, b) => a.y - b.y)
        .map((item, index) => (
          <ParkDecoration key={`${item.kind}-${index}`} {...item} />
        ))}
    </g>
  );
}
