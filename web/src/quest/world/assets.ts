import * as THREE from "three";

type Shape = "box" | "sphere" | "cone" | "cylinder" | "rock" | "ring" | "roof" | "yurtRoof";

export class WorldAssets {
  private geometries = new Map<Shape, THREE.BufferGeometry>();
  private materials = new Map<string, THREE.MeshLambertMaterial>();

  geometry(shape: Shape): THREE.BufferGeometry {
    const cached = this.geometries.get(shape);
    if (cached) return cached;
    const factories: Record<Shape, () => THREE.BufferGeometry> = {
      box: () => new THREE.BoxGeometry(1, 1, 1),
      sphere: () => new THREE.SphereGeometry(1, 24, 16),
      cone: () => new THREE.ConeGeometry(1, 1, 32),
      cylinder: () => new THREE.CylinderGeometry(1, 1, 1, 64),
      rock: () => new THREE.IcosahedronGeometry(1, 0),
      ring: () => new THREE.TorusGeometry(1, 0.09, 5, 24),
      yurtRoof: () => new THREE.LatheGeometry([
        new THREE.Vector2(1, -.5), new THREE.Vector2(.88, -.22),
        new THREE.Vector2(.62, .12), new THREE.Vector2(.32, .4),
        new THREE.Vector2(.12, .5), new THREE.Vector2(0, .5),
      ], 48),
      roof: () => new THREE.ConeGeometry(1, 1, 4),
    };
    const geometry = factories[shape]();
    this.geometries.set(shape, geometry);
    return geometry;
  }

  material(color: string, flatShading = false): THREE.MeshLambertMaterial {
    const key = `${color}:${flatShading}`;
    if (!this.materials.has(key))
      this.materials.set(
        key,
        new THREE.MeshLambertMaterial({ color, flatShading }),
      );
    return this.materials.get(key)!;
  }

  mesh(
    parent: THREE.Object3D,
    shape: Shape,
    color: string,
    position: [number, number, number],
    scale: [number, number, number],
  ): THREE.Mesh {
    const mesh = new THREE.Mesh(this.geometry(shape), this.material(color, shape === "rock" || shape === "roof"));
    mesh.position.set(...position);
    mesh.scale.set(...scale);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    parent.add(mesh);
    return mesh;
  }

  dispose() {
    this.geometries.forEach((g) => g.dispose());
    this.materials.forEach((m) => m.dispose());
  }
}

export function seededRandom(seed: number) {
  return () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 4294967296;
  };
}
