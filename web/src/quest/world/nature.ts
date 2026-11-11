import { type ModelId, type ModelPlacement } from "../../graphics/models";
import { TARGETS } from "../types";
import { seededRandom } from "./assets";

export interface NatureBatch {
  model: ModelId;
  placements: ModelPlacement[];
}

export function forestBatches(positions: readonly [number, number, number][]): NatureBatch[] {
  const models: ModelId[] = ["pine", "oak", "broadleaf"];
  return models.map((model, variant) => ({
    model,
    placements: positions.filter((_, i) => i % models.length === variant)
      .map(([x, z, height], i) => ({ x, z, height, rotation: i * 2.399 })),
  }));
}

export function meadowBatches(): NatureBatch[] {
  const random = seededRandom(318);
  const models: ModelId[] = ["grass", "lavender", "flower", "bush", "rock", "boulder"];
  const batches: NatureBatch[] = models.map((model) => ({ model, placements: [] }));
  for (let i = 0; i < 125; i++) {
    const angle = random() * Math.PI * 2;
    const radius = 9.5 + random() * 10.5;
    const x = Math.cos(angle) * radius;
    const z = Math.sin(angle) * radius;
    if (TARGETS.some((target) => Math.hypot(target.x - x, target.z - z) < 3.5)) continue;
    if (Math.abs(x) < 2.6 || (Math.abs(z + 4) < 2.7 && Math.abs(x) < 14)) continue;
    const index = i % models.length;
    batches[index].placements.push({
      x, z, height: index < 3 ? 0.2 + random() * 0.28 : 0.35 + random() * 0.4,
      rotation: random() * Math.PI * 2,
    });
  }
  batches.push({ model: "lily", placements: [
    { x: 13.7, z: -6, y: 0.12, height: 0.12 },
    { x: 10.5, z: -6.4, y: 0.12, height: 0.1, rotation: 1 },
    { x: 14, z: -3.8, y: 0.12, height: 0.15, rotation: 2.3 },
  ] });
  return batches;
}
