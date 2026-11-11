import { money } from "./format";
import * as THREE from "three";
import { ModelLibrary, type ModelPlacement } from "../graphics/models";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { WorldAssets, seededRandom } from "../quest/world/assets";
import type { Board, Match, Move } from "./types";

export function tilePoint(index: number, count: number): [number, number] {
  const side = count / 4,
    step = 3.15,
    half = (side * step) / 2;
  if (index <= side) return [half - index * step, half];
  if (index <= side * 2) return [-half, half - (index - side) * step];
  if (index <= side * 3) return [-half + (index - side * 2) * step, -half];
  return [half, -half + (index - side * 3) * step];
}
function wrap(
  ctx: CanvasRenderingContext2D,
  text: string,
  width: number,
): string[] {
  const lines: string[] = [];
  let line = "";
  for (const word of text.split(" ")) {
    const next = line ? `${line} ${word}` : word;
    if (ctx.measureText(next).width > width && line) {
      lines.push(line);
      line = word;
    } else line = next;
  }
  if (line) lines.push(line);
  return lines.slice(0, 3);
}
function labelTexture(
  name: string,
  color: string,
  price: string,
  kind: string,
): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 256;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = "#fff9e9";
  ctx.fillRect(0, 0, 256, 256);
  ctx.fillStyle = color;
  ctx.fillRect(0, 0, 256, 38);
  ctx.fillStyle = "#fff9e9";
  for (let i = 0; i < 8; i++) {
    ctx.save();
    ctx.translate(i * 36 + 2, 18);
    ctx.rotate(Math.PI / 4);
    ctx.strokeStyle = "#fff9e9b0";
    ctx.lineWidth = 3;
    ctx.strokeRect(-7, -7, 14, 14);
    ctx.restore();
  }
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = "#334e46";
  ctx.font = "600 24px Inter, sans-serif";
  const lines = wrap(ctx, name, 225);
  lines.forEach((line, i) => ctx.fillText(line, 128, 96 + i * 30));
  ctx.font = "500 25px Inter, sans-serif";
  ctx.fillStyle = "#9b8150";
  ctx.fillText(price, 128, 216);
  if (kind === "chance") {
    ctx.font = "bold 58px Georgia";
    ctx.fillStyle = "#b9954d";
    ctx.fillText("?", 128, 163);
  }
  if (kind === "start") {
    ctx.font = "45px Georgia";
    ctx.fillStyle = "#49978a";
    ctx.fillText("➜", 128, 163);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  return texture;
}
function yurt(
  a: WorldAssets,
  g: THREE.Group,
  x: number,
  z: number,
  scale: number,
  color: string,
) {
  const m = a.mesh.bind(a);
  const root = new THREE.Group();
  root.position.set(x, 0, z);
  root.scale.setScalar(scale);
  g.add(root);
  m(root, "cylinder", "#f7e9c8", [0, 0.6, 0], [1.25, 1.2, 1.25]);
  m(root, "yurtRoof", color, [0, 1.65, 0], [1.42, 0.95, 1.42]);
  m(root, "cylinder", "#d8b76d", [0, 1.05, 0], [1.27, 0.12, 1.27]);
  m(root, "box", "#487b72", [0, 0.45, 1.25], [0.5, 0.9, 0.04]);
  m(root, "cylinder", "#705846", [0, 2.16, 0], [0.2, 0.12, 0.2]);
}
export class BoardWorld {
  private scene = new THREE.Scene();
  private assets = new WorldAssets();
  private renderer: THREE.WebGLRenderer;
  private camera = new THREE.OrthographicCamera(-20, 20, 17, -17, 0.1, 180);
  private controls: OrbitControls;
  private observer: ResizeObserver;
  private map = new THREE.Group();
  private property = new THREE.Group();
  private pawns = new THREE.Group();
  private decorations = new THREE.Group();
  private clouds = new THREE.Group();
  private textures: THREE.Texture[] = [];
  private materials: THREE.Material[] = [];
  private pointerStart: { x: number; y: number } | null = null;
  private ray = new THREE.Raycaster();
  private point = new THREE.Vector2();
  private listeners = new AbortController();
  private frame = 0;
  private last = 0;
  private paused = false;
  private disposed = false;
  private models = new ModelLibrary();
  private board: Board | null = null;
  private signature = "";
  private previousMoves: Move[] = [];
  private queue: {
    player: number;
    positions: number[];
    step: number;
    elapsed: number;
  }[] = [];
  private pawnGroups: THREE.Group[] = [];
  private selected: THREE.Group;
  private animation = false;
  private finalPositions: number[] = [];
  private readonly reducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)",
  ).matches;
  private rotation = 0.0;
  constructor(
    private host: HTMLElement,
    private onSelect: (index: number) => void,
    private onAnimate: (active: boolean) => void,
    private onError: () => void,
  ) {
    this.renderer = new THREE.WebGLRenderer({
      antialias: window.innerWidth > 700,
      powerPreference: "low-power",
    });
    this.renderer.setPixelRatio(
      Math.min(devicePixelRatio, window.innerWidth < 700 ? 1.25 : 1.5),
    );
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 0.9;
    this.renderer.shadowMap.enabled = window.innerWidth > 700;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.domElement.style.touchAction = "none";
    this.renderer.domElement.setAttribute(
      "aria-label",
      "Кликабельді 3D ойын алаңы. Ұяшықты басып, кәсіп туралы ақпаратты ашыңыз.",
    );
    host.appendChild(this.renderer.domElement);
    this.scene.add(new THREE.HemisphereLight("#fff7e4", "#7a9b8b", 1.9));
    const sun = new THREE.DirectionalLight("#fff1ca", 2.5);
    sun.position.set(-16, 30, 18);
    sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024);
    Object.assign(sun.shadow.camera, {
      left: -24,
      right: 24,
      top: 24,
      bottom: -24,
      near: 1,
      far: 80,
    });
    sun.shadow.normalBias = 0.08;
    this.scene.add(
      sun,
      this.map,
      this.property,
      this.pawns,
      this.decorations,
      this.clouds,
    );
    this.selected = new THREE.Group();
    this.scene.add(this.selected);
    for (const sign of [-1, 1]) {
      this.assets.mesh(
        this.selected,
        "box",
        "#e8bb64",
        [sign * 1.48, 0, 0],
        [0.07, 0.09, 3],
      );
      this.assets.mesh(
        this.selected,
        "box",
        "#e8bb64",
        [0, 0, sign * 1.48],
        [3, 0.09, 0.07],
      );
    }
    this.selected.visible = false;
    this.camera.zoom = window.innerWidth < 700 ? 1 : 1.15;
    this.camera.position.set(18, 31, 24);
    this.camera.lookAt(0, 0, 0);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enablePan = false;
    this.controls.enableDamping = false;
    this.controls.minPolarAngle = 0.3;
    this.controls.maxPolarAngle = 0.85;
    this.controls.minZoom = 0.7;
    this.controls.maxZoom = 1.7;
    this.controls.enableZoom = true;
    this.controls.addEventListener("change", this.draw);
    const options = { signal: this.listeners.signal };
    this.renderer.domElement.addEventListener(
      "pointerdown",
      (event) => {
        this.pointerStart = { x: event.clientX, y: event.clientY };
      },
      options,
    );
    this.renderer.domElement.addEventListener(
      "pointerup",
      this.pointerUp,
      options,
    );
    this.renderer.domElement.addEventListener(
      "webglcontextlost",
      (event) => {
        event.preventDefault();
        this.pause(true);
        this.onError();
      },
      options,
    );
    document.addEventListener("visibilitychange", this.visibility, options);
    this.observer = new ResizeObserver(this.resize);
    this.observer.observe(host);
    this.resize();
    this.schedule();
  }
  private resize = () => {
    const { width, height } = this.host.getBoundingClientRect();
    if (!width || !height) return;
    const aspect = width / height;
    const span =
      (aspect < 1 ? 17 / aspect : 15.8) *
      ((this.board?.tiles.length ?? 24) / 24);
    if (width < 700 && this.camera.zoom > 1) this.camera.zoom = 1;
    this.camera.left = -span * aspect;
    this.camera.right = span * aspect;
    this.camera.top = span;
    this.camera.bottom = -span;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
    this.draw();
  };
  private draw = () => {
    if (!this.disposed) this.renderer.render(this.scene, this.camera);
  };
  private pointerUp = (event: PointerEvent) => {
    const start = this.pointerStart;
    this.pointerStart = null;
    if (
      this.paused ||
      !start ||
      Math.hypot(event.clientX - start.x, event.clientY - start.y) > 9
    )
      return;
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.point.set(
      ((event.clientX - rect.left) / rect.width) * 2 - 1,
      (-(event.clientY - rect.top) / rect.height) * 2 + 1,
    );
    this.ray.setFromCamera(this.point, this.camera);
    for (const hit of this.ray.intersectObjects(
      [...this.map.children, ...this.property.children],
      true,
    )) {
      let node: THREE.Object3D | null = hit.object;
      while (node && node.userData.tile === undefined) node = node.parent;
      if (node && typeof node.userData.tile === "number") {
        this.onSelect(node.userData.tile);
        return;
      }
    }
  };
  private reset() {
    this.models.dispose();
    this.models = new ModelLibrary();
    this.map.clear();
    this.property.clear();
    this.decorations.clear();
    this.clouds.clear();
    this.textures.forEach((t) => t.dispose());
    this.materials.forEach((m) => m.dispose());
    this.textures = [];
    this.materials = [];
    this.previousMoves = [];
    this.queue = [];
    this.signature = "";
    this.selected.visible = false;
  }
  setBoard(board: Board) {
    if (this.board?.id === board.id) return;
    this.reset();
    this.board = board;
    this.scene.background = new THREE.Color(board.sky);
    this.scene.fog = new THREE.Fog(board.sky, 65, 120);
    const a = this.assets,
      m = a.mesh.bind(a),
      n = board.tiles.length,
      half = ((n / 4) * 3.15) / 2;
    const mat = this.assets.material(board.ground);
    const base = m(
      this.map,
      "box",
      "#e1d2ad",
      [0, -0.65, 0],
      [half * 2 + 4, 1.3, half * 2 + 4],
    );
    base.receiveShadow = true;
    m(
      this.map,
      "box",
      board.ground,
      [0, 0.04, 0],
      [half * 2 + 3.8, 0.2, half * 2 + 3.8],
    );
    board.tiles.forEach((tile, index) => {
      const [x, z] = tilePoint(index, n);
      const group = new THREE.Group();
      group.position.set(x, 0.25, z);
      group.userData.tile = index;
      this.map.add(group);
      m(group, "box", "#d1bf99", [0, 0.0, 0], [2.98, 0.34, 2.98]);
      const texture = labelTexture(
        tile.name,
        tile.color,
        tile.price
          ? money(tile.price)
          : tile.kind === "tax"
            ? money(tile.amount)
            : tile.kind === "rest"
              ? `+${money(tile.amount)}`
              : "",
        tile.kind,
      );
      this.textures.push(texture);
      const material = new THREE.MeshLambertMaterial({ map: texture });
      this.materials.push(material);
      const top = new THREE.Mesh(this.assets.geometry("box"), material);
      top.scale.set(2.88, 0.04, 2.88);
      top.position.y = 0.2;
      group.add(top);
      if (tile.kind === "station") {
        m(group, "box", "#68878c", [0, 0.37, -0.78], [1.1, 0.3, 0.38]);
        for (const dx of [-0.38, 0.38])
          m(group, "cylinder", "#485c57", [dx, 0.23, -0.78], [0.1, 0.15, 0.1]);
      }
    });
    const center = m(
      this.decorations,
      "box",
      board.ground,
      [0, 0.08, 0],
      [half * 2 - 3.6, 0.1, half * 2 - 3.6],
    );
    center.material = mat;
    const random = seededRandom(
      board.id.split("").reduce((s, c) => s + c.charCodeAt(0), 734),
    );
    const treeFallback = new THREE.Group();
    const forest = new THREE.Group();
    this.decorations.add(treeFallback, forest);
    const treePlacements: ModelPlacement[] = [];
    for (let i = 0; i < 28; i++) {
      const angle = random() * Math.PI * 2,
        r = 2.5 + random() * (half - 5),
        x = Math.cos(angle) * r,
        z = Math.sin(angle) * r;
      if (Math.abs(x) < 2 && Math.abs(z) < 2) continue;
      const h = 0.55 + random() * 0.7;
      treePlacements.push({ x, z, y: 0.14, height: h * 1.8, rotation: random() * 6.28 });
      m(
        treeFallback,
        "cylinder",
        "#907956",
        [x, h * 0.35, z],
        [0.04, h * 0.7, 0.04],
      );
      m(
        treeFallback,
        "sphere",
        i % 2 ? "#83aa7b" : "#9dbb82",
        [x, h + 0.2, z],
        [0.4, 0.6, 0.4],
      );
      if (board.biome === "almaty" && i % 3 === 0)
        m(
          treeFallback,
          "sphere",
          "#cf8864",
          [x + 0.25, h + 0.2, z],
          [0.11, 0.11, 0.11],
        );
    }
    void Promise.all([
      this.models.batch("oak", treePlacements.filter((_, i) => i % 2 === 0)),
      this.models.batch("pine", treePlacements.filter((_, i) => i % 2 === 1)),
    ]).then((groups) => {
      if (this.disposed || forest.parent !== this.decorations || groups.some((group) => !group)) return;
      treeFallback.visible = false;
      groups.forEach((group) => forest.add(group!));
      this.draw();
    });
    if (board.biome === "almaty") {
      for (let i = 0; i < 5; i++) {
        const height = 2 + random() * 2.5;
        m(
          this.decorations,
          "cone",
          "#a7bebb",
          [-4 + i * 1.9, height / 2, -4.6],
          [1.9, height, 1.9],
        );
        m(
          this.decorations,
          "cone",
          "#f2f1dc",
          [-4 + i * 1.9, height * 0.87, -4.6],
          [0.65, height * 0.3, 0.65],
        );
      }
      const lake = m(
        this.decorations,
        "cylinder",
        "#7dbfc1",
        [2.5, 0.16, -1.8],
        [1.4, 0.06, 1],
      );
      lake.receiveShadow = false;
      m(
        this.decorations,
        "cylinder",
        "#b09a74",
        [-2, 1.9, -2],
        [0.1, 3.8, 0.1],
      );
      m(this.decorations, "sphere", "#d5b76d", [-2, 3.9, -2], [0.5, 0.35, 0.5]);
    } else if (board.biome === "astana") {
      m(
        this.decorations,
        "cylinder",
        "#e9e5ce",
        [0, 0.25, -2],
        [1.15, 0.5, 1.15],
      );
      for (let i = 0; i < 6; i++) {
        const angle = (i * Math.PI) / 3;
        const column = m(
          this.decorations,
          "cylinder",
          "#dfd6ba",
          [Math.cos(angle) * 0.4, 1.9, -2 + Math.sin(angle) * 0.4],
          [0.06, 3.2, 0.06],
        );
        column.rotation.z = -Math.cos(angle) * 0.12;
      }
      m(this.decorations, "sphere", "#d4b164", [0, 3.8, -2], [0.8, 0.8, 0.8]);
      m(this.decorations, "cone", "#b9cfcc", [-3, 1.3, -3], [1.5, 2.6, 1.5]);
      m(
        this.decorations,
        "cylinder",
        "#e0ce9f",
        [-3, 2.7, -3],
        [0.05, 0.7, 0.05],
      );
      for (let i = 0; i < 4; i++) {
        m(
          this.decorations,
          "box",
          i % 2 ? "#bfd0cf" : "#d8d9c5",
          [3.8, 0.9 + i * 0.2, -4 + i * 1.8],
          [1.1, 1.8 + i * 0.4, 1],
        );
      }
    } else if (board.biome === "turkistan") {
      m(this.decorations, "box", "#d0b68a", [0, 1.1, -3], [3, 2.2, 2.5]);
      m(this.decorations, "sphere", "#69aeb1", [0, 2.5, -3], [1.15, 1.1, 1.15]);
      m(this.decorations, "cone", "#d9b96c", [0, 3.6, -3], [0.12, 0.4, 0.12]);
      for (const x of [-1.8, 1.8]) {
        m(
          this.decorations,
          "cylinder",
          "#d9bd8e",
          [x, 1.6, -2],
          [0.27, 3.2, 0.27],
        );
        m(this.decorations, "cone", "#6caaa9", [x, 3.4, -2], [0.35, 0.5, 0.35]);
      }
      m(
        this.decorations,
        "box",
        "#678f94",
        [0, 0.85, -1.72],
        [1.15, 1.7, 0.08],
      );
    } else {
      yurt(a, this.decorations, -2, -3, 0.8, "#cb9467");
      yurt(a, this.decorations, 2, -3, 0.6, "#769e91");
      for (let i = 0; i < 3; i++) {
        m(
          this.decorations,
          "box",
          "#9e8765",
          [-3 + i * 3, 0.15, 0.7],
          [1.6, 0.12, 1.3],
        );
        for (let j = 0; j < 5; j++)
          m(
            this.decorations,
            "rock",
            "#c3b35d",
            [
              -3 + i * 3 + (j % 3) * 0.3 - 0.3,
              0.4,
              0.7 + Math.floor(j / 3) * 0.3,
            ],
            [0.09, 0.25, 0.09],
          );
      }
    }
    const banner = labelTexture(
      "ДАЛА ДӘУЛЕТІ",
      "#c3a460",
      "ҚҰР · ДАМЫТ · ГҮЛДЕН",
      "title",
    );
    this.textures.push(banner);
    const labelMat = new THREE.MeshLambertMaterial({ map: banner });
    this.materials.push(labelMat);
    const sign = new THREE.Mesh(this.assets.geometry("box"), labelMat);
    sign.position.set(0, 0.17, 2.5);
    sign.scale.set(5.2, 0.03, 3.4);
    this.decorations.add(sign);
    for (let i = 0; i < 4; i++) {
      const cloud = new THREE.Group();
      cloud.position.set(-7 + i * 5, 7 + i * 0.5, -8);
      for (let j = 0; j < 3; j++)
        m(cloud, "sphere", "#f6f2df", [j * 0.65, 0, 0], [0.8, 0.32, 0.5]);
      this.clouds.add(cloud);
    }
    this.resize();
  }
  setSelection(index: number) {
    if (!this.board || index < 0) {
      this.selected.visible = false;
      return;
    }
    const [x, z] = tilePoint(index, this.board.tiles.length);
    this.selected.position.set(x, 0.51, z);
    this.selected.visible = true;
    this.draw();
  }
  update(match: Match | null, preview = false) {
    if (!this.board) return;
    const signature = JSON.stringify([match?.lots, preview]);
    const board = this.board,
      a = this.assets,
      m = a.mesh.bind(a);
    if (signature !== this.signature) {
      this.property.clear();
      board.tiles.forEach((tile, index) => {
        const lot = match?.lots[index];
        if (!lot && !(preview && tile.kind === "property" && index % 4 === 1))
          return;
        const [x, z] = tilePoint(index, board.tiles.length);
        const group = new THREE.Group();
        group.position.set(x, 0, z);
        group.userData.tile = index;
        this.property.add(group);
        const color = lot ? match!.players[lot.owner].color : tile.color;
        const owned = m(
          group,
          "box",
          lot?.mortgaged ? "#a7aba1" : color,
          [0, 0.52, 1.28],
          [2.85, 0.07, 0.22],
        );
        owned.castShadow = false;
        const level = lot?.level ?? (preview ? 2 : 0);
        if (!level) {
          m(group, "cylinder", color, [0.9, 0.7, -0.85], [0.15, 0.3, 0.15]);
          return;
        }
        if (level === tile.rents.length - 1) {
          m(group, "box", "#f1e5c8", [0, 1.2, -0.45], [1.7, 1.4, 1.1]);
          m(group, "roof", color, [0, 2.1, -0.45], [1.5, 0.7, 1]);
          for (const x of [-0.5, 0, 0.5])
            m(group, "box", "#dfbf6e", [x, 1.25, 0.12], [0.2, 0.35, 0.03]);
        } else
          for (let h = 0; h < level; h++) {
            const x = (h - (level - 1) / 2) * 0.65;
            if (board.biome === "steppe") yurt(a, group, x, -0.75, 0.23, color);
            else {
              m(group, "box", "#efe4c8", [x, 0.81, -0.75], [0.52, 0.55, 0.6]);
              m(group, "roof", color, [x, 1.2, -0.75], [0.46, 0.35, 0.55]);
            }
          }
      });
      this.signature = signature;
    }
    this.finalPositions = match?.players.map((player) => player.position) ?? [];
    const moves = match?.moves ?? [];
    if (this.pawnGroups.length !== (match?.players.length ?? 0)) {
      this.pawns.clear();
      this.pawnGroups = [];
      match?.players.forEach((player, i) => {
        const group = new THREE.Group();
        this.pawns.add(group);
        m(group, "cylinder", player.color, [0, 0.14, 0], [0.3, 0.18, 0.3]);
        m(group, "cone", player.color, [0, 0.5, 0], [0.3, 0.7, 0.3]);
        m(group, "sphere", "#f6e5bd", [0, 0.95, 0], [0.2, 0.22, 0.2]);
        m(group, "cone", player.color, [0, 1.22, 0], [0.25, 0.4, 0.25]);
        m(group, "rock", "#f2cc6d", [0, 1.44, 0], [0.06, 0.12, 0.06]);
        this.pawnGroups.push(group);
        this.place(i, player.position);
      });
      this.previousMoves = structuredClone(moves);
    } else if (match) {
      let overlap = 0;
      for (
        let n = Math.min(this.previousMoves.length, moves.length);
        n > 0;
        n--
      )
        if (
          JSON.stringify(this.previousMoves.slice(-n)) ===
          JSON.stringify(moves.slice(0, n))
        ) {
          overlap = n;
          break;
        }
      const fresh = moves.slice(overlap);
      if (JSON.stringify(moves) !== JSON.stringify(this.previousMoves)) {
        for (const move of fresh) {
          const positions = Array.from(
            { length: move.steps + 1 },
            (_, i) => (move.start + i) % board.tiles.length,
          );
          this.queue.push({
            player: move.player,
            positions,
            step: 0,
            elapsed: 0,
          });
        }
        this.previousMoves = structuredClone(moves);
      }
      if (!this.queue.length)
        match.players.forEach((player, i) => this.place(i, player.position));
      match.players.forEach((p, i) => {
        this.pawnGroups[i].visible = !p.bankrupt;
      });
    }
    if (this.reducedMotion) {
      this.queue = [];
      this.finalPositions.forEach((position, index) =>
        this.place(index, position),
      );
    }
    if (this.queue.length && !this.animation) {
      this.animation = true;
      this.onAnimate(true);
    }
    this.draw();
  }
  private place(player: number, tile: number, height = 0) {
    if (!this.board || !this.pawnGroups[player]) return;
    const [x, z] = tilePoint(tile, this.board.tiles.length);
    this.pawnGroups[player].position.set(
      x + (player % 2 ? -0.42 : 0.42),
      0.5 + height,
      z + (player < 2 ? -0.22 : 0.22),
    );
  }
  rotate() {
    this.rotation += 0.25;
    const distance = 30;
    this.camera.position.set(
      Math.sin(0.65 + this.rotation) * distance,
      31,
      Math.cos(0.65 + this.rotation) * distance,
    );
    this.controls.update();
    this.draw();
  }
  zoom(delta: number) {
    this.camera.zoom = THREE.MathUtils.clamp(
      this.camera.zoom + delta,
      0.7,
      1.7,
    );
    this.camera.updateProjectionMatrix();
    this.draw();
  }
  pause(value: boolean) {
    this.paused = value;
    this.controls.enabled = !value;
    cancelAnimationFrame(this.frame);
    this.frame = 0;
    this.last = 0;
    if (!value) this.schedule();
  }
  private visibility = () => {
    cancelAnimationFrame(this.frame);
    this.frame = 0;
    this.last = 0;
    if (!document.hidden) this.schedule();
  };
  private schedule() {
    if (!this.disposed && !this.paused && !document.hidden && !this.frame)
      this.frame = requestAnimationFrame(this.tick);
  }
  private tick = (time: number) => {
    this.frame = 0;
    if (this.disposed || this.paused || document.hidden) return;
    if (time - this.last > 33) {
      const dt = this.last ? Math.min(time - this.last, 100) : 0;
      this.last = time;
      this.clouds.children.forEach((cloud, i) => {
        if (!this.reducedMotion)
          cloud.position.x = -7 + i * 5 + Math.sin(time * 0.00008 + i) * 0.6;
      });
      const move = this.queue[0];
      if (move && this.board) {
        move.elapsed += dt;
        const duration = 110;
        while (
          move.elapsed >= duration &&
          move.step < move.positions.length - 1
        ) {
          move.elapsed -= duration;
          move.step++;
        }
        if (move.step >= move.positions.length - 1) {
          this.place(move.player, move.positions.at(-1)!);
          this.queue.shift();
        } else {
          const t = move.elapsed / duration;
          const from = tilePoint(
              move.positions[move.step],
              this.board.tiles.length,
            ),
            to = tilePoint(
              move.positions[move.step + 1],
              this.board.tiles.length,
            ),
            group = this.pawnGroups[move.player];
          if (group)
            group.position.set(
              THREE.MathUtils.lerp(from[0], to[0], t) +
                (move.player % 2 ? -0.42 : 0.42),
              0.5 + Math.sin(t * Math.PI) * 0.45,
              THREE.MathUtils.lerp(from[1], to[1], t) +
                (move.player < 2 ? -0.22 : 0.22),
            );
        }
      }
      if (!this.queue.length && this.animation) {
        this.animation = false;
        this.finalPositions.forEach((position, index) =>
          this.place(index, position),
        );
        this.onAnimate(false);
      }
      this.draw();
    }
    this.schedule();
  };
  dispose() {
    this.disposed = true;
    cancelAnimationFrame(this.frame);
    this.observer.disconnect();
    this.listeners.abort();
    this.controls.removeEventListener("change", this.draw);
    this.controls.dispose();
    this.models.dispose();
    this.assets.dispose();
    this.textures.forEach((t) => t.dispose());
    this.materials.forEach((m) => m.dispose());
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}
