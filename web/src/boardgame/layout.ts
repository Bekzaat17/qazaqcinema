export type Point = { x: number; y: number };

function boardPoint(index: number, count: number): Point {
  const side = count / 4, step = 600 / side, half = 300;
  const normalized = ((index % count) + count) % count;
  if (normalized <= side) return { x: half - normalized * step, y: half };
  if (normalized <= side * 2) return { x: -half, y: half - (normalized - side) * step };
  if (normalized <= side * 3) return { x: -half + (normalized - side * 2) * step, y: -half };
  return { x: half, y: -half + (normalized - side * 3) * step };
}
function project({ x, y: z }: Point, painted: boolean): Point {
  return painted ? { x: 500 + x * 1.2, y: 500 + z * 1.2 }
    : { x: 500 + (x - z) * .7, y: 420 + (x + z) * .36 };
}
export function illustratedPoint(index: number, count: number, painted = false): Point {
  return project(boardPoint(index, count), painted);
}
export function cellCorners(index: number, count: number): Point[] {
  const center = boardPoint(index, count), half = 300 / (count / 4);
  return [[-half, -half], [half, -half], [half, half], [-half, half]]
    .map(([x, y]) => project({ x: center.x + x, y: center.y + y }, true));
}
