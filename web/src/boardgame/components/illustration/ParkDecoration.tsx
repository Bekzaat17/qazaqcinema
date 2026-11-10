export type ParkObject =
  | "bench"
  | "lamp"
  | "tree"
  | "apple"
  | "flowers"
  | "lawn"
  | "fountain"
  | "spruce";

const SPRITES: Record<ParkObject, number> = {
  bench: 0,
  lamp: 1,
  tree: 2,
  apple: 3,
  flowers: 4,
  lawn: 5,
  fountain: 6,
  spruce: 7,
};

export interface ParkPlacement {
  kind: ParkObject;
  x: number;
  y: number;
  size: number;
}

export default function ParkDecoration({ kind, x, y, size }: ParkPlacement) {
  const sprite = SPRITES[kind];
  const foliage = kind === "tree" || kind === "apple" || kind === "spruce";
  return (
    <g transform={`translate(${x} ${y})`}>
      <g className={foliage ? "dala-park-foliage" : undefined}>
        <svg
          x={-size / 2}
          y={-size * 0.9}
          width={size}
          height={size}
          viewBox={`${(sprite % 4) * 100 + 1} ${Math.floor(sprite / 4) * 100 + 1} 98 98`}
          overflow="hidden"
        >
          <image
            href="/boardgame/art/park-props-v1.webp"
            width="400"
            height="200"
            preserveAspectRatio="none"
          />
        </svg>
      </g>
    </g>
  );
}
