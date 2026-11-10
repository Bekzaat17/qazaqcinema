export interface Point {
  x: number;
  z: number;
}
export interface Obstacle extends Point {
  radius: number;
}
const STEP = 0.7;
const LIMIT = 20.7;
const key = (point: Point) => `${point.x},${point.z}`;
const distance = (a: Point, b: Point) => Math.hypot(a.x - b.x, a.z - b.z);

export function canWalk(
  point: Point,
  obstacles: Obstacle[],
  clearance = 0.35,
): boolean {
  return (
    Math.hypot(point.x, point.z) < LIMIT &&
    !obstacles.some(
      (obstacle) => distance(point, obstacle) < obstacle.radius + clearance,
    )
  );
}

/** A* работает только при выборе цели; кадры получают готовые путевые точки. */
export function findPath(
  start: Point,
  destination: Point,
  obstacles: Obstacle[],
): Point[] {
  const snap = (point: Point): Point => ({
    x: Math.round(point.x / STEP),
    z: Math.round(point.z / STEP),
  });
  const world = (point: Point): Point => ({
    x: point.x * STEP,
    z: point.z * STEP,
  });
  const origin = snap(start),
    goal = snap(destination);
  const open: Point[] = [origin];
  const previous = new Map<string, Point>();
  const cost = new Map<string, number>([[key(origin), 0]]);
  const closed = new Set<string>();
  const directions = [-1, 0, 1].flatMap((x) =>
    [-1, 0, 1].filter((z) => x || z).map((z) => ({ x, z })),
  );
  while (open.length && closed.size < 4000) {
    let best = 0;
    for (let i = 1; i < open.length; i++) {
      if (
        cost.get(key(open[i]))! + distance(open[i], goal) <
        cost.get(key(open[best]))! + distance(open[best], goal)
      )
        best = i;
    }
    const current = open.splice(best, 1)[0];
    if (distance(world(current), destination) < 0.9) {
      const path: Point[] = [];
      let cursor: Point | undefined = current;
      while (cursor && key(cursor) !== key(origin)) {
        path.unshift(world(cursor));
        cursor = previous.get(key(cursor));
      }
      if (canWalk(destination, obstacles, 0.45)) path.push(destination);
      return path;
    }
    closed.add(key(current));
    for (const direction of directions) {
      const next = { x: current.x + direction.x, z: current.z + direction.z };
      if (closed.has(key(next)) || !canWalk(world(next), obstacles, 0.5))
        continue;
      if (
        direction.x &&
        direction.z &&
        (!canWalk(world({ x: next.x, z: current.z }), obstacles, 0.5) ||
          !canWalk(world({ x: current.x, z: next.z }), obstacles, 0.5))
      )
        continue;
      const nextCost =
        cost.get(key(current))! + Math.hypot(direction.x, direction.z);
      if (nextCost >= (cost.get(key(next)) ?? Infinity)) continue;
      cost.set(key(next), nextCost);
      previous.set(key(next), current);
      if (!open.some((point) => key(point) === key(next))) open.push(next);
    }
  }
  return [];
}
