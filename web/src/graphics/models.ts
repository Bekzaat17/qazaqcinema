import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const MATERIAL_PALETTE: Record<string, string> = {
  leafsGreen: "#6b9c77", leafsDark: "#3d725d", grass: "#87a773",
  woodBark: "#957052", woodBarkDark: "#715840", stone: "#a5aa9a",
};
const KENNEY = "/models/kenney-nature/";
const QUATERNIUS = "/models/quaternius-nature/";
export const MODEL_CATALOG = {
  oak: `${QUATERNIUS}CommonTree_1.glb`,
  broadleaf: `${QUATERNIUS}Birch_1.glb`,
  pine: `${QUATERNIUS}GiantPine_1.glb`,
  rock: `${KENNEY}rock-largea.glb`,
  boulder: `${KENNEY}rock-largeb.glb`,
  bush: `${QUATERNIUS}Bush_Common.glb`,
  lavender: `${KENNEY}flower-purplea.glb`,
  flower: `${KENNEY}flower-yellowa.glb`,
  grass: `${QUATERNIUS}Grass_Common_Short.glb`,
  firepit: `${KENNEY}campfire-stones.glb`,
  logs: `${KENNEY}log-stack.glb`,
  pot: `${KENNEY}pot-large.glb`,
  pumpkin: `${KENNEY}crop-pumpkin.glb`,
  wheat: `${KENNEY}crops-wheatstageb.glb`,
  fence: `${KENNEY}fence-simple.glb`,
  lily: `${KENNEY}lily-large.glb`,
} as const;
export type ModelId = keyof typeof MODEL_CATALOG;
export interface ModelPlacement {
  x: number;
  z: number;
  y?: number;
  height: number;
  rotation?: number;
}

function releaseModel(root: THREE.Object3D) {
  const geometries = new Set<THREE.BufferGeometry>();
  const materials = new Set<THREE.Material>();
  const textures = new Set<THREE.Texture>();
  root.traverse((node) => {
    if (!(node instanceof THREE.Mesh)) return;
    geometries.add(node.geometry);
    for (const material of Array.isArray(node.material) ? node.material : [node.material]) {
      materials.add(material);
      for (const value of Object.values(material)) {
        if (value instanceof THREE.Texture) textures.add(value);
      }
    }
  });
  textures.forEach((texture) => texture.dispose());
  materials.forEach((material) => material.dispose());
  geometries.forEach((geometry) => geometry.dispose());
}

// Адаптер отделяет игровые названия и размеры от структуры стороннего набора.
// Ресурсы принадлежат экземпляру библиотеки, а не отдельным копиям моделей.
export class ModelLibrary {
  private loader = new GLTFLoader();
  private templates = new Map<ModelId, Promise<THREE.Group | null>>();
  private batches: THREE.InstancedMesh[] = [];
  private disposed = false;
  private wind = { value: 0 };

  private load(id: ModelId): Promise<THREE.Group | null> {
    let pending = this.templates.get(id);
    if (!pending) {
      pending = this.loader.loadAsync(MODEL_CATALOG[id])
        .then(({ scene }) => {
          if (this.disposed) {
            releaseModel(scene);
            return null;
          }
          // Исходные материалы набора металлические; без окружения они чернеют.
          // Растительность и камень приводим к общей матовой палитре мира.
          scene.traverse((node) => {
            if (!(node instanceof THREE.Mesh)) return;
            for (const material of Array.isArray(node.material) ? node.material : [node.material]) {
              if (!(material instanceof THREE.MeshStandardMaterial)) continue;
              material.metalness = 0;
              material.roughness = 0.9;
              if (/Leaves/.test(material.name)) {
                material.emissive.set("#647445");
                material.emissiveIntensity = 0.22;
                material.onBeforeCompile = (shader) => {
                  shader.uniforms.uModelWind = this.wind;
                  shader.vertexShader = "uniform float uModelWind;\n" + shader.vertexShader;
                  shader.vertexShader = shader.vertexShader.replace("#include <begin_vertex>", `
                    #include <begin_vertex>
                    transformed.x += sin(uModelWind * .9 + position.x * .7 + position.y * .4)
                      * .018 * max(position.y, 0.0);
                  `);
                };
              }
              if (MATERIAL_PALETTE[material.name])
                material.color.set(MATERIAL_PALETTE[material.name]);
            }
          });
          scene.updateMatrixWorld(true);
          return scene;
        })
        .catch((error: unknown) => {
          console.warn(`Не удалось загрузить модель ${id}`, error);
          return null;
        });
      this.templates.set(id, pending);
    }
    return pending;
  }

  async batch(id: ModelId, placements: readonly ModelPlacement[]): Promise<THREE.Group | null> {
    if (this.disposed || !placements.length) return null;
    const template = await this.load(id);
    if (!template || this.disposed) return null;
    const bounds = new THREE.Box3().setFromObject(template);
    const center = bounds.getCenter(new THREE.Vector3());
    const height = Math.max(bounds.max.y - bounds.min.y, 0.001);
    const normalize = new THREE.Matrix4().makeTranslation(-center.x, -bounds.min.y, -center.z);
    const group = new THREE.Group();
    group.name = `model:${id}`;
    const transform = new THREE.Object3D();
    const matrix = new THREE.Matrix4();
    template.traverse((node) => {
      if (!(node instanceof THREE.Mesh)) return;
      const mesh = new THREE.InstancedMesh(node.geometry, node.material, placements.length);
      placements.forEach((placement, index) => {
        transform.position.set(placement.x, placement.y ?? 0, placement.z);
        transform.rotation.set(0, placement.rotation ?? 0, 0);
        transform.scale.setScalar(placement.height / height);
        transform.updateMatrix();
        matrix.copy(transform.matrix).multiply(normalize).multiply(node.matrixWorld);
        mesh.setMatrixAt(index, matrix);
      });
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      mesh.computeBoundingSphere();
      group.add(mesh);
      this.batches.push(mesh);
    });
    return group;
  }

  animate(time: number) { this.wind.value = time; }

  dispose() {
    if (this.disposed) return;
    this.disposed = true;
    this.batches.forEach((mesh) => mesh.dispose());
    this.batches = [];
    this.templates.forEach((pending) => {
      void pending.then((root) => { if (root) releaseModel(root); });
    });
    this.templates.clear();
  }
}
