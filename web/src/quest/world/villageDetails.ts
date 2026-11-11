import * as THREE from "three";
import { type ModelId, type ModelPlacement, ModelLibrary } from "../../graphics/models";
import type { BuildingId } from "../types";
import { WorldAssets } from "./assets";

export function villageDetails(
  assets: WorldAssets,
  models: ModelLibrary,
  parent: THREE.Group,
  id: BuildingId,
  level: number,
) {
  if (!level) return;
  const details = new THREE.Group();
  parent.add(details);
  const m = assets.mesh.bind(assets);
  const add = (model: ModelId, placements: ModelPlacement[]) => {
    void models.batch(model, placements).then((group) => {
      if (group && details.parent === parent) details.add(group);
    });
  };
  if (id === "yurt") {
    m(details, "box", "#b75f47", [0, 0.13, 2.05], [1.05, 0.035, 0.65]);
    for (const x of [-0.32, 0, 0.32]) {
      const motif = m(details, "box", "#edce87", [x, 0.155, 2.05], [0.17, 0.012, 0.17]);
      motif.rotation.y = Math.PI / 4;
    }
    // Пояс и рёбра крыши следуют окружности юрты.
    for (let i = 0; i < 12; i++) {
      const angle = i * Math.PI / 6;
      const rib = m(details, "box", "#e6b584", [Math.sin(angle) * 0.96, 1.8 + level * 0.16,
        Math.cos(angle) * 0.96], [0.035, 0.035, 1.72]);
      rib.rotation.set(0.58, angle, 0);
    }
    add("pot", [{ x: 1.4, z: 1.5, height: 0.48 }]);
    if (level >= 2) {
      add("firepit", [{ x: -1.55, z: -1.5, height: 0.22 }]);
      m(details, "box", "#b28a5e", [-1.85, 0.36, -0.7], [0.7, 0.16, 0.3]);
    }
  } else if (id === "well") {
    for (let i = 0; i < 10; i++) {
      const angle = i * Math.PI / 5;
      const stone = m(details, "box", "#e3dcc5", [Math.cos(angle) * 1.05, 0.76,
        Math.sin(angle) * 1.05], [0.49, 0.18, 0.25]);
      stone.rotation.y = -angle + Math.PI / 2;
    }
    const axle = m(details, "cylinder", "#856047", [0, 1.6, 0], [0.08, 2.5, 0.08]);
    axle.rotation.z = Math.PI / 2;
    m(details, "cylinder", "#d5bb80", [0, 1.35, 0], [0.024, 0.5, 0.024]);
    add("pot", [{ x: 1.25, z: 1.25, height: 0.45 }]);
    if (level >= 2) {
      add("flower", [{ x: -1.6, z: -0.8, height: 0.42 }, { x: -1.8, z: -0.5, height: 0.3 }]);
    }
  } else {
    m(details, "box", "#be975e", [1.1, 0.7, 1.55], [1.2, 0.12, 0.6]);
    for (const x of [0.65, 1.55])
      m(details, "box", "#7e6048", [x, 0.35, 1.55], [0.08, 0.7, 0.08]);
    add("logs", [{ x: -1.4, z: 0.6, height: 0.6, rotation: Math.PI / 2 }]);
    add("pot", [{ x: 1.1, z: 1.55, y: 0.77, height: 0.25 }]);
    if (level >= 2) {
      const awning = m(details, "box", "#5f9385", [0, 1.8, 1.5], [2.6, 0.08, 1]);
      awning.rotation.x = 0.14;
      for (const x of [-1.2, 1.2])
        m(details, "cylinder", "#8b6848", [x, 0.85, 1.9], [0.04, 1.7, 0.04]);
    }
  }
  if (level >= 2) {
    add("fence", [{ x: 0, z: -2, height: 0.65 },
      { x: -1.5, z: -1.6, height: 0.65, rotation: Math.PI / 2 }]);
    add("lavender", [{ x: 1.5, z: -1.5, height: 0.4 },
      { x: 1.2, z: -1.7, height: 0.35 }]);
  }
  if (level >= 3) {
    m(details, "box", "#866846", [1.4, 0.14, -1.1], [0.8, 0.14, 0.9]);
    add("wheat", [{ x: 1.4, z: -1.3, y: 0.2, height: 0.55 },
      { x: 1.65, z: -1.1, y: 0.2, height: 0.5 }]);
    add("pumpkin", [{ x: 1.3, z: -0.85, y: 0.2, height: 0.25 }]);
  }
}
