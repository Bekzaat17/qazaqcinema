import * as THREE from "three";
import { ModelLibrary } from "../../graphics/models";
import { villageDetails } from "./villageDetails";
import { PLOTS, type BuildingId, type Progress } from "../types";
import { WorldAssets } from "./assets";

function createBuilding(
  assets: WorldAssets,
  group: THREE.Group,
  id: BuildingId,
  level: number,
) {
  const m = assets.mesh.bind(assets);
  m(group, "cylinder", "#c6b788", [0, 0.05, 0], [2.1, 0.12, 2.1]);
  if (level === 0) {
    for (let i = 0; i < 4; i++) {
      const a = (i * Math.PI) / 2 + Math.PI / 4;
      m(
        group,
        "cylinder",
        "#ad8c5c",
        [Math.cos(a) * 1.6, 0.35, Math.sin(a) * 1.6],
        [0.09, 0.7, 0.09],
      );
    }
    const ring = m(group, "ring", "#f9e7b3", [0, 0.2, 0], [1.5, 1.5, 1.5]);
    ring.rotation.x = -Math.PI / 2;
    return;
  }
  const height = 1 + level * 0.16;
  if (id === "yurt") {
    m(group, "cylinder", "#fff1cc", [0, height / 2, 0], [1.6, height, 1.6]);
    m(group, "yurtRoof", "#d27d5a", [0, height + 0.55, 0], [1.82, 1.15, 1.82]);
    m(group, "cylinder", "#efc775", [0, height - 0.13, 0], [1.62, 0.14, 1.62]);
    m(group, "box", "#285c58", [0, 0.5, 1.6], [0.62, 1, 0.12]);
    m(group, "cylinder", "#493e4c", [0, height + 1.15, 0], [0.3, 0.12, 0.3]);
    for (let i = 0; i < level + 2; i++) {
      const a = (i * Math.PI) / 2;
      const deco = m(
        group,
        "box",
        "#c6654d",
        [Math.sin(a) * 1.61, 0.6, Math.cos(a) * 1.61],
        [0.2, 0.2, 0.06],
      );
      deco.rotation.set(0, a, Math.PI / 4);
    }
  } else if (id === "well") {
    m(group, "cylinder", "#c2c9bd", [0, 0.45, 0], [1.15, 0.8, 1.15]);
    m(group, "cylinder", "#59bcbc", [0, 0.87, 0], [0.85, 0.02, 0.85]);
    for (const x of [-1.1, 1.1])
      m(group, "box", "#806c58", [x, 1.15, 0], [0.14, 2.3, 0.14]);
    const roof = m(group, "roof", "#5a8f79", [0, 2.4, 0], [1.8, 1, 1.8]);
    roof.rotation.y = Math.PI / 4;
    m(group, "cylinder", "#bda06a", [0, 1.35, 0], [0.3, 0.4, 0.3]);
  } else {
    m(group, "box", "#bb9066", [0, 0.85, 0], [2.5, 1.7, 2]);
    const roof = m(group, "roof", "#846c97", [0, 2, 0], [2.2, 1.5, 2]);
    roof.rotation.y = Math.PI / 4;
    m(group, "box", "#493f50", [0, 0.6, 1.02], [0.7, 1.2, 0.08]);
    m(group, "box", "#ffe3a1", [0.82, 1, 1.02], [0.5, 0.5, 0.08]);
    m(group, "box", "#8c806e", [0.8, 2.3, -0.4], [0.4, 1.4, 0.4]);
  }
  if (level >= 2) {
    for (const x of [-1.8, 1.8]) {
      m(group, "cylinder", "#726e52", [x, 0.5, 1.6], [0.06, 1, 0.06]);
      m(group, "rock", "#ffdd85", [x, 1.1, 1.6], [0.2, 0.3, 0.2]);
    }
  }
  if (level >= 3) {
    m(group, "cylinder", "#b18a50", [-1.8, 1.9, -0.5], [0.05, 3.8, 0.05]);
    m(group, "box", "#3ba6a0", [-1.3, 3.4, -0.5], [1, 0.65, 0.03]);
    m(group, "rock", "#eac77c", [-1.3, 3.4, -0.47], [0.16, 0.2, 0.04]);
  }
}

export class VillageView {
  private models = new ModelLibrary();
  private levels = new Map<string, number>();
  private groups = new Map<string, THREE.Group>();
  constructor(
    private scene: THREE.Scene,
    private assets: WorldAssets,
  ) {
    for (const plot of PLOTS) {
      const group = new THREE.Group();
      group.position.set(plot.x, 0, plot.z);
      scene.add(group);
      this.groups.set(plot.id, group);
      createBuilding(assets, group, plot.id as BuildingId, 0);
    }
  }
  update(progress: Progress) {
    for (const building of progress.buildings) {
      if (this.levels.get(building.id) === building.level) continue;
      const group = this.groups.get(building.id)!;
      group.clear();
      createBuilding(this.assets, group, building.id, building.level);
      villageDetails(this.assets, this.models, group, building.id, building.level);
      this.levels.set(building.id, building.level);
    }
  }
  animate(time: number) { this.models.animate(time); }
  dispose() {
    this.models.dispose();
    this.groups.forEach((group) => this.scene.remove(group));
  }
}
