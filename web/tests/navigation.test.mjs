import assert from "node:assert/strict";
import test from "node:test";
import { canWalk, findPath } from "../src/quest/world/navigation.ts";

test("маршрут обходит деревья и приводит к святилищу", () => {
  const obstacles = [
    { x: -6, z: -2, radius: 1.5 },
    { x: -8, z: -4, radius: 1 },
  ];
  const route = findPath({ x: 0, z: 5 }, { x: -11, z: -3.1 }, obstacles);
  assert.ok(route.length > 0);
  for (const point of route) assert.ok(canWalk(point, obstacles));
  assert.ok(Math.hypot(route.at(-1).x + 11, route.at(-1).z + 3.1) < 1);
});

test("граница острова и недостижимая цель не обходятся", () => {
  assert.equal(canWalk({ x: 25, z: 0 }, []), false);
  assert.deepEqual(findPath({ x: 0, z: 0 }, { x: 40, z: 0 }, []), []);
});

test("маршрут не пересекает углы препятствий", () => {
  const obstacles = [
    { x: 1, z: 0, radius: 0.6 },
    { x: 0, z: 1, radius: 0.6 },
  ];
  const route = findPath({ x: 0, z: 0 }, { x: 4, z: 4 }, obstacles);
  assert.ok(route.length > 0);
  let previous = { x: 0, z: 0 };
  for (const next of route) {
    for (let i = 0; i <= 10; i++)
      assert.ok(
        canWalk(
          {
            x: previous.x + ((next.x - previous.x) * i) / 10,
            z: previous.z + ((next.z - previous.z) * i) / 10,
          },
          obstacles,
        ),
      );
    previous = next;
  }
});
