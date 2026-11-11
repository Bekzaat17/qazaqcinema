import * as THREE from "three";
import { ModelLibrary } from "../../graphics/models";
import { forestBatches, meadowBatches } from "./nature";
import { PLOTS, SHRINES, TARGETS, type Progress } from "../types";
import { seededRandom, WorldAssets } from "./assets";
import { TerrainView } from "./terrain";
import { VillageView } from "./village";

export interface Obstacle {
  x: number;
  z: number;
  radius: number;
}

export class QuestScene {
  readonly scene = new THREE.Scene();
  readonly assets = new WorldAssets();
  private models = new ModelLibrary();
  private disposed = false;
  readonly hero = new THREE.Group();
  readonly companion = new THREE.Group();
  readonly ground: THREE.Mesh;
  readonly terrain: TerrainView;
  readonly obstacles: Obstacle[] = [];
  readonly sun = new THREE.DirectionalLight("#fff2cf", 3.1);
  readonly village: VillageView;
  readonly destination: THREE.Mesh;
  private legs: THREE.Mesh[] = [];
  private spirits: THREE.Group[] = [];
  private particles: THREE.Points;
  private pulse: THREE.Mesh;
  private pulseAge = 10;
  private treeObstacleCount = 0;
  private particleGeometry = new THREE.BufferGeometry();
  private particleMaterial = new THREE.PointsMaterial({
    color: "#fff5b8",
    size: 0.09,
    transparent: true,
    opacity: 0.8,
  });

  constructor() {
    const { scene, assets } = this;
    const m = assets.mesh.bind(assets);
    scene.background = new THREE.Color("#d5e4dc");
    scene.fog = new THREE.Fog("#d5e4dc", 55, 115);
    scene.add(new THREE.HemisphereLight("#f5eeff", "#67765d", 2.5));
    this.sun.position.set(-14, 27, 12);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(1024, 1024);
    Object.assign(this.sun.shadow.camera, {
      left: -25,
      right: 25,
      top: 25,
      bottom: -25,
      near: 1,
      far: 70,
    });
    this.sun.shadow.normalBias = 0.08;
    scene.add(this.sun);
    m(scene, "cylinder", "#8e9785", [0, -2.3, 0], [22, 4, 22]);
    m(scene, "cylinder", "#a7b78a", [0, -0.5, 0], [22.2, 0.6, 22.2]);
    this.terrain = new TerrainView(scene);
    this.ground = this.terrain.ground;
    const random = seededRandom(7341);
    for (let i = 0; i < 9; i++) {
      const a = (i / 9) * Math.PI * 2;
      m(
        scene,
        "cone",
        i % 2 ? "#bdcfd1" : "#c9cedb",
        [Math.cos(a) * 65, 1, Math.sin(a) * 65],
        [18 + random() * 10, 19 + random() * 18, 16],
      );
    }
    this.makeTrees(random);
    this.treeObstacleCount = this.obstacles.length;
    for (const target of TARGETS) {
      for (let j = 1; j < 12; j++) {
        const t = j / 12;
        const stone = m(
          scene,
          "cylinder",
          j % 3 ? "#acaa8d" : "#beb79a",
          [target.x * t + (random() - 0.5) * 0.4, 0.04, 5 + (target.z - 5) * t],
          [0.22 + random() * 0.18, 0.06, 0.22],
        );
        stone.rotation.y = random() * 6;
      }
    }
    m(scene, "cylinder", "#6cbfc0", [12, 0.01, -5], [4, 0.1, 4.5]);
    m(scene, "cylinder", "#8ed9cc", [12, 0.08, -5], [3.4, 0.04, 3.9]);
    for (let i = 0; i < 7; i++)
      m(scene, "box", "#d2b98b", [8 + i * 0.7, 0.18, -3], [0.6, 0.14, 1.5]);
    for (const shrine of SHRINES) {
      const group = new THREE.Group();
      group.position.set(shrine.x, 0, shrine.z);
      scene.add(group);
      m(group, "cylinder", "#bbbca9", [0, 0.15, 0], [1.7, 0.3, 1.7]);
      m(group, "cylinder", "#d7d6b9", [0, 0.38, 0], [1.3, 0.2, 1.3]);
      for (const x of [-1.2, 1.2]) {
        m(group, "box", "#8d9c91", [x, 1.6, 0], [0.55, 2.5, 0.6]);
        m(group, "rock", "#d5d5bb", [x, 3, 0], [0.5, 0.4, 0.5]);
      }
      m(group, "box", "#adbba7", [0, 2.85, 0], [2.8, 0.4, 0.7]);
      const spirit = new THREE.Group();
      spirit.position.y = 1.7;
      group.add(spirit);
      m(spirit, "rock", shrine.color, [0, 0, 0], [0.5, 0.75, 0.5]);
      m(spirit, "sphere", "#ffffff", [-0.12, 0.08, 0.4], [0.055, 0.07, 0.05]);
      m(spirit, "sphere", "#ffffff", [0.12, 0.08, 0.4], [0.055, 0.07, 0.05]);
      const halo = m(
        spirit,
        "ring",
        shrine.color,
        [0, 0, 0],
        [0.85, 0.85, 0.85],
      );
      halo.rotation.x = Math.PI / 2;
      this.spirits.push(spirit);
    }
    // Шаңырақ — цель главы: просыпается после трёх духов.
    m(scene, "cylinder", "#b5ba9b", [0, 0.3, -20], [2, 0.5, 2]);
    const portal = m(scene, "ring", "#dab782", [0, 2.8, -20], [2.5, 2.5, 2.5]);
    portal.name = "portal";
    for (const x of [-2.2, 2.2])
      m(scene, "cylinder", "#a2a78c", [x, 1.5, -20], [0.3, 3, 0.3]);
    this.village = new VillageView(scene, assets);
    this.makeHero();
    const positions = new Float32Array(180 * 3);
    for (let i = 0; i < positions.length; i += 3) {
      positions[i] = (random() - 0.5) * 38;
      positions[i + 1] = 0.5 + random() * 5;
      positions[i + 2] = (random() - 0.5) * 38;
    }
    this.particleGeometry.setAttribute(
      "position",
      new THREE.BufferAttribute(positions, 3),
    );
    this.particles = new THREE.Points(
      this.particleGeometry,
      this.particleMaterial,
    );
    scene.add(this.particles);
    this.destination = m(
      scene,
      "ring",
      "#fff2c9",
      [0, 0.16, 0],
      [0.4, 0.4, 0.4],
    );
    this.destination.rotation.x = -Math.PI / 2;
    this.destination.visible = false;
    this.pulse = m(scene, "ring", "#b3f4e7", [0, 0.25, 0], [1, 1, 1]);
    this.pulse.rotation.x = -Math.PI / 2;
    this.pulse.visible = false;
  }

  private makeTrees(random: () => number) {
    const positions: [number, number, number][] = [];
    for (let attempt = 0; attempt < 600 && positions.length < 65; attempt++) {
      const x = (random() - 0.5) * 42,
        z = (random() - 0.5) * 42;
      if (
        Math.hypot(x, z) > 21 ||
        Math.hypot(x, z - 4) < 9 ||
        TARGETS.some((t) => Math.hypot(t.x - x, t.z - z) < 3.4)
      )
        continue;
      if (Math.abs(x) < 2.6 || (Math.abs(z + 4) < 2.7 && Math.abs(x) < 14))
        continue;
      positions.push([x, z, 2.2 + random() * 2.4]);
      this.obstacles.push({ x, z, radius: 0.55 });
    }
    const fallback = new THREE.Group();
    this.scene.add(fallback);
    const matrix = new THREE.Object3D();
    const parts = [
      {
        shape: "cylinder" as const,
        color: "#76694f",
        height: 0.4,
        width: 0.1,
        offset: 0.25,
      },
      {
        shape: "cone" as const,
        color: "#527c61",
        height: 0.85,
        width: 0.43,
        offset: 0.65,
      },
      {
        shape: "cone" as const,
        color: "#6d9372",
        height: 0.7,
        width: 0.34,
        offset: 1,
      },
      {
        shape: "cone" as const,
        color: "#8bad7d",
        height: 0.5,
        width: 0.22,
        offset: 1.3,
      },
    ];
    for (const part of parts) {
      const mesh = new THREE.InstancedMesh(
        this.assets.geometry(part.shape),
        this.assets.material(part.color),
        positions.length,
      );
      positions.forEach(([x, z, h], index) => {
        matrix.position.set(x, h * part.offset, z);
        matrix.scale.set(h * part.width, h * part.height, h * part.width);
        matrix.updateMatrix();
        mesh.setMatrixAt(index, matrix.matrix);
      });
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      fallback.add(mesh);
    }
    const flowers = new THREE.InstancedMesh(
      this.assets.geometry("rock"),
      this.assets.material("#f0ce94"),
      170,
    );
    for (let i = 0; i < 170; i++) {
      const a = random() * Math.PI * 2,
        r = 9 + random() * 11;
      matrix.position.set(Math.cos(a) * r, 0.15, Math.sin(a) * r);
      matrix.scale.set(0.08, 0.18, 0.08);
      matrix.updateMatrix();
      flowers.setMatrixAt(i, matrix.matrix);
    }
    fallback.add(flowers);
    // Геометрический лес остаётся доступным при ошибке сети или загрузки GLB.
    void Promise.all(forestBatches(positions).map(({ model, placements }) =>
      this.models.batch(model, placements),
    )).then((groups) => {
      if (this.disposed || groups.some((group) => !group)) return;
      fallback.visible = false;
      groups.forEach((group) => this.scene.add(group!));
    });
    for (const { model, placements } of meadowBatches()) {
      void this.models.batch(model, placements).then((group) => {
        if (group && !this.disposed) this.scene.add(group);
      });
    }
  }

  private makeHero() {
    const m = this.assets.mesh.bind(this.assets);
    this.hero.position.set(0, 0, 5);
    this.scene.add(this.hero);
    for (const x of [-0.15, 0.15])
      this.legs.push(
        m(this.hero, "box", "#394959", [x, 0.24, 0], [0.18, 0.48, 0.23]),
      );
    m(this.hero, "cone", "#348f89", [0, 0.78, 0], [0.43, 0.94, 0.36]);
    m(this.hero, "cylinder", "#deb769", [0, 0.65, 0], [0.34, 0.09, 0.3]);
    m(this.hero, "sphere", "#e9bd92", [0, 1.35, 0], [0.27, 0.3, 0.26]);
    m(this.hero, "sphere", "#3d3d4c", [0, 1.52, -0.06], [0.29, 0.21, 0.26]);
    m(this.hero, "sphere", "#394052", [-0.1, 1.37, 0.23], [0.025, 0.04, 0.025]);
    m(this.hero, "sphere", "#394052", [0.1, 1.37, 0.23], [0.025, 0.04, 0.025]);
    m(this.hero, "cone", "#297b7d", [0, 1.72, -0.01], [0.34, 0.4, 0.3]);
    m(this.hero, "rock", "#f4d284", [0, 1.9, -0.01], [0.08, 0.17, 0.08]);
    m(this.hero, "cylinder", "#967459", [0.48, 0.9, 0.15], [0.045, 1.8, 0.045]);
    m(this.hero, "rock", "#b2f4dc", [0.48, 1.9, 0.15], [0.17, 0.23, 0.17]);
    m(this.hero, "sphere", "#e9bd92", [0.4, 0.9, 0.15], [0.12, 0.12, 0.12]);
    this.scene.add(this.companion);
    m(this.companion, "sphere", "#c3a9e8", [0, 0, 0], [0.28, 0.35, 0.28]);
    for (const x of [-0.12, 0.12])
      m(
        this.companion,
        "sphere",
        "#fff8eb",
        [x, 0.08, 0.22],
        [0.06, 0.08, 0.04],
      );
    for (const x of [-0.17, 0.17])
      m(this.companion, "cone", "#a88bcf", [x, 0.36, 0], [0.12, 0.3, 0.12]);
  }

  cast() {
    this.pulseAge = 0;
    this.pulse.position.copy(this.hero.position);
    this.pulse.position.y = 0.3;
  }
  progress(progress: Progress) {
    this.village.update(progress);
    this.obstacles.splice(this.treeObstacleCount);
    for (const building of progress.buildings) {
      const plot = PLOTS.find((value) => value.id === building.id);
      if (plot && building.level > 0)
        this.obstacles.push({
          x: plot.x,
          z: plot.z,
          radius: building.id === "well" ? 1.15 : 1.6,
        });
    }
    this.spirits.forEach((spirit, i) => {
      spirit.scale.setScalar(
        progress.completed_quests.includes(
          SHRINES[i].id as "forest" | "river" | "sky",
        )
          ? 1.25
          : 1,
      );
    });
    const portal = this.scene.getObjectByName("portal") as THREE.Mesh;
    portal.material = this.assets.material(
      progress.completed_quests.length === 3 ? "#b7f8dc" : "#dab782",
    );
  }
  animate(time: number, dt: number, moving: boolean) {
    this.terrain.animate(time);
    this.models.animate(time);
    this.village.animate(time);
    this.spirits.forEach((s, i) => {
      s.position.y = 1.7 + Math.sin(time * 1.7 + i) * 0.15;
      s.rotation.y = Math.sin(time * 0.6 + i) * 0.2;
    });
    this.legs.forEach((leg, i) => {
      leg.rotation.x = moving ? Math.sin(time * 13 + i * Math.PI) * 0.5 : 0;
    });
    this.companion.position.set(
      this.hero.position.x + 1,
      1.75 + Math.sin(time * 3) * 0.13,
      this.hero.position.z - 0.5,
    );
    this.companion.rotation.y = Math.sin(time) * 0.3;
    this.particles.rotation.y = time * 0.015;
    this.pulseAge += dt;
    this.pulse.visible = this.pulseAge < 0.7;
    if (this.pulse.visible) this.pulse.scale.setScalar(0.3 + this.pulseAge * 6);
  }
  dispose() {
    this.disposed = true;
    this.models.dispose();
    this.village.dispose();
    this.terrain.dispose();
    this.particleGeometry.dispose();
    this.particleMaterial.dispose();
    this.scene.traverse((object) => {
      if (object instanceof THREE.InstancedMesh && !object.parent?.name.startsWith("model:"))
        object.dispose();
    });
    this.assets.dispose();
    this.scene.clear();
  }
}
