import * as THREE from "three";
import { PLOTS, TARGETS, type Quality } from "../types";
import { seededRandom } from "./assets";

const SIZE = 1024;
const WORLD = 44;
const pixel = (value: number) => (value / WORLD + 0.5) * SIZE;

export function distanceToPath(x: number, z: number) {
  return Math.min(...TARGETS.map((target) => {
    const dx = target.x, dz = target.z - 5;
    const t = Math.max(0, Math.min(1, (x * dx + (z - 5) * dz) / (dx * dx + dz * dz)));
    return Math.hypot(x - t * dx, z - (5 + t * dz));
  }));
}

function groundTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = SIZE;
  const ctx = canvas.getContext("2d")!;
  const random = seededRandom(986);
  const data = ctx.createImageData(SIZE, SIZE);
  for (let y = 0; y < SIZE; y++) {
    for (let x = 0; x < SIZE; x++) {
      const shade = Math.sin(x * .026) * Math.cos(y * .019) * 8
        + Math.sin((x + y) * .011) * 5 + (random() - .5) * 14;
      const i = (y * SIZE + x) * 4;
      data.data[i] = 94 + shade;
      data.data[i + 1] = 131 + shade;
      data.data[i + 2] = 61 + shade * .6;
      data.data[i + 3] = 255;
    }
  }
  ctx.putImageData(data, 0, 0);
  // Несколько полупрозрачных слоёв дают мягкие вытоптанные края без сетки плиток.
  for (const target of TARGETS) {
    for (let width = 42; width >= 18; width -= 4) {
      ctx.beginPath();
      ctx.moveTo(pixel(0), pixel(5));
      ctx.quadraticCurveTo(pixel(target.x * .45 + .35), pixel(5 + (target.z - 5) * .5),
        pixel(target.x), pixel(target.z));
      ctx.strokeStyle = width > 26 ? "#aeaa6d16" : "#c5b17c35";
      ctx.lineWidth = width;
      ctx.lineCap = "round";
      ctx.stroke();
    }
  }
  for (const plot of PLOTS) {
    const radius = SIZE / WORLD * 2.4;
    const gradient = ctx.createRadialGradient(pixel(plot.x), pixel(plot.z), 0,
      pixel(plot.x), pixel(plot.z), radius);
    gradient.addColorStop(0, plot.id === "well" ? "#838c6c" : "#bba574");
    gradient.addColorStop(.55, "#b2a579bb");
    gradient.addColorStop(1, "#b2a57900");
    ctx.fillStyle = gradient;
    ctx.fillRect(pixel(plot.x) - radius, pixel(plot.z) - radius, radius * 2, radius * 2);
  }
  for (let i = 0; i < 42000; i++) {
    const x = random() * SIZE, y = random() * SIZE;
    ctx.strokeStyle = i % 3 ? "#e7e3a126" : "#355d352b";
    ctx.lineWidth = .5 + random() * .6;
    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + random() * 2 - 1, y - 1 - random() * 3); ctx.stroke();
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  return texture;
}

function bladeGeometry() {
  const vertices: number[] = [];
  const colors: number[] = [];
  for (let blade = 0; blade < 4; blade++) {
    const a = blade * 2.399;
    const height = .55 + (blade % 3) * .15;
    const points = [
      [-.035, 0, 0], [.035, 0, 0], [.018, height * .55, .035],
      [-.035, 0, 0], [.018, height * .55, .035], [-.025, height * .55, .035],
      [-.025, height * .55, .035], [.018, height * .55, .035], [.07, height, .1],
    ];
    for (const [x, y, z] of points) {
      vertices.push(x * Math.cos(a) + z * Math.sin(a), y, z * Math.cos(a) - x * Math.sin(a));
      const color = new THREE.Color().setHSL(.23, .3, .22 + y * .28);
      colors.push(color.r, color.g, color.b);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  geometry.computeVertexNormals();
  return geometry;
}

export class TerrainView {
  readonly ground: THREE.Mesh;
  private texture = groundTexture();
  private grass: THREE.InstancedMesh;
  private wind = { value: 0 };
  private materials: THREE.Material[] = [];
  private geometries: THREE.BufferGeometry[] = [];

  constructor(private scene: THREE.Scene) {
    const surface = new THREE.MeshStandardMaterial({ map: this.texture, roughness: 1 });
    const circle = new THREE.CircleGeometry(22, 128);
    circle.rotateX(-Math.PI / 2);
    this.ground = new THREE.Mesh(circle, surface);
    this.ground.position.y = .015;
    this.ground.receiveShadow = true;
    scene.add(this.ground);
    const blades = bladeGeometry();
    const material = new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide });
    material.onBeforeCompile = (shader) => {
      shader.uniforms.uWind = this.wind;
      shader.vertexShader = "uniform float uWind;\n" + shader.vertexShader;
      shader.vertexShader = shader.vertexShader.replace("#include <begin_vertex>", `
        #include <begin_vertex>
        #ifdef USE_INSTANCING
          float phase = uWind * 1.4 + instanceMatrix[3].x * .6 + instanceMatrix[3].z * .35;
          transformed.x += sin(phase) * position.y * position.y * .17;
          transformed.z += cos(phase * .7) * position.y * position.y * .08;
        #endif
      `);
    };
    this.grass = new THREE.InstancedMesh(blades, material, 6000);
    const random = seededRandom(5318);
    const matrix = new THREE.Object3D();
    let count = 0;
    for (let attempt = 0; attempt < 30000 && count < 6000; attempt++) {
      const x = (random() - .5) * 42, z = (random() - .5) * 42;
      if (Math.hypot(x, z) > 21 || distanceToPath(x, z) < .8 ||
        TARGETS.some((t) => Math.hypot(t.x - x, t.z - z) < 2.5) ||
        Math.hypot(x - 12, (z + 5) / 1.1) < 4.4) continue;
      matrix.position.set(x, .04, z);
      matrix.rotation.y = random() * Math.PI * 2;
      const scale = .25 + random() * .52;
      matrix.scale.set(scale * 1.3, scale, scale * 1.3);
      matrix.updateMatrix();
      this.grass.setMatrixAt(count++, matrix.matrix);
    }
    this.grass.count = count;
    this.grass.userData.maxCount = count;
    this.grass.receiveShadow = true;
    this.grass.computeBoundingSphere();
    scene.add(this.grass);
    this.materials.push(surface, material);
    this.geometries.push(circle, blades);
  }
  setQuality(quality: Quality) {
    this.grass.count = Math.min(this.grass.userData.maxCount, quality === "low" ? 3000 : 6000);
  }
  animate(time: number) { this.wind.value = time; }
  dispose() {
    this.scene.remove(this.ground, this.grass);
    this.grass.dispose();
    this.materials.forEach((material) => material.dispose());
    this.geometries.forEach((geometry) => geometry.dispose());
    this.texture.dispose();
  }
}
