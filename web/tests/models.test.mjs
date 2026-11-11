import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import test from "node:test";
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { MODEL_CATALOG, ModelLibrary } from "../src/graphics/models.ts";

test("каждая модель локальна, совпадает с источником и содержит корректный GLB", async () => {
  const loader = new GLTFLoader();
  for (const source of Object.values(MODEL_CATALOG)) {
    assert.ok(source.startsWith("/models/"));
    const url = new URL(`../public${source}`, import.meta.url);
    const manifest = JSON.parse(await readFile(new URL("sources.json", url), "utf8"));
    assert.equal(manifest.license, "CC0-1.0");
    const record = manifest.models.find((model) => model.file === source.split("/").at(-1));
    assert.ok(record, source);
    const buffer = await readFile(url);
    assert.equal(createHash("sha256").update(buffer).digest("hex"), record.sha256);
    assert.equal(buffer.readUInt32LE(0), 0x46546c67);
    assert.equal(buffer.readUInt32LE(8), buffer.length);
    const jsonLength = buffer.readUInt32LE(12);
    const doc = JSON.parse(buffer.subarray(20, 20 + jsonLength).toString());
    assert.ok(doc.meshes.length > 0);
    assert.ok(doc.buffers.every((entry) => !entry.uri));
    for (const image of doc.images ?? []) {
      assert.equal(image.uri, undefined);
      assert.ok(doc.bufferViews[image.bufferView].byteLength > 0);
    }
    if (!doc.images?.length) {
      const array = buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
      const { scene } = await loader.parseAsync(array, "");
      const bounds = new THREE.Box3().setFromObject(scene);
      assert.ok(bounds.max.y > bounds.min.y, source);
    }
  }
});

test("адаптер выравнивает основание, высоту и центр моделей разных масштабов", async () => {
  const library = new ModelLibrary();
  let calls = 0;
  library.loader.loadAsync = async () => {
    calls++;
    const scene = new THREE.Group();
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(2, 4, 2), new THREE.MeshStandardMaterial({ metalness: 1 }));
    mesh.position.set(10, 4, -8);
    scene.add(mesh);
    return { scene };
  };
  const group = await library.batch("oak", [{ x: 3, z: 7, y: 0.5, height: 2, rotation: 1 }]);
  assert.equal(group.children[0].material.metalness, 0);
  const bounds = new THREE.Box3().setFromObject(group);
  assert.ok(Math.abs(bounds.min.y - 0.5) < 1e-6);
  assert.ok(Math.abs(bounds.max.y - 2.5) < 1e-6);
  const center = bounds.getCenter(new THREE.Vector3());
  assert.ok(Math.abs(center.x - 3) < 1e-6);
  assert.ok(Math.abs(center.z - 7) < 1e-6);
  await library.batch("oak", [{ x: 0, z: 0, height: 1 }]);
  assert.equal(calls, 1);
  library.dispose();
});

test("поздняя загрузка после ухода освобождается и не создаёт объекты", async () => {
  const library = new ModelLibrary();
  let finish;
  const scene = new THREE.Group();
  const geometry = new THREE.BoxGeometry();
  const material = new THREE.MeshBasicMaterial();
  let released = 0;
  geometry.addEventListener("dispose", () => released++);
  material.addEventListener("dispose", () => released++);
  scene.add(new THREE.Mesh(geometry, material));
  library.loader.loadAsync = () => new Promise((resolve) => { finish = resolve; });
  const pending = library.batch("oak", [{ x: 0, z: 0, height: 1 }]);
  library.dispose();
  finish({ scene });
  assert.equal(await pending, null);
  assert.equal(released, 2);
  assert.equal(await library.batch("pine", [{ x: 0, z: 0, height: 1 }]), null);
});
