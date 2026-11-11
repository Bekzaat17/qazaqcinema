import * as THREE from "three";
import {
  TARGETS,
  type Progress,
  type Quality,
  type WorldTarget,
} from "../types";
import { QuestScene } from "./scene";
import { canWalk, findPath, type Point } from "./navigation";

interface WorldEvents {
  near(target: WorldTarget | null): void;
  interact(): void;
  error(): void;
}

export class QuestEngine {
  private readonly world = new QuestScene();
  private readonly renderer: THREE.WebGLRenderer;
  private readonly camera = new THREE.OrthographicCamera(
    -30,
    30,
    25,
    -25,
    0.1,
    160,
  );
  private readonly observer: ResizeObserver;
  private readonly listeners = new AbortController();
  private readonly keys = new Set<string>();
  private readonly raycaster = new THREE.Raycaster();
  private readonly move = new THREE.Vector3();
  private readonly focus = new THREE.Vector3(-8, 0, 1);
  private readonly offset = new THREE.Vector3(25, 31, 30);
  private destination: THREE.Vector3 | null = null;
  private route: Point[] = [];
  private joystick = { x: 0, y: 0 };
  private frame = 0;
  private last = 0;
  private time = 0;
  private nearId = "";
  private playing = false;
  private paused = false;
  private disposed = false;
  private quality: Quality;
  private pointer: { x: number; y: number } | null = null;

  constructor(
    private host: HTMLElement,
    private events: WorldEvents,
    quality: Quality,
  ) {
    this.quality = quality;
    try {
      this.renderer = new THREE.WebGLRenderer({
        antialias: quality === "high",
        powerPreference: "low-power",
      });
    } catch (error) {
      this.world.dispose();
      throw error;
    }
    this.renderer.setClearColor("#d5e4dc");
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.domElement.setAttribute(
      "aria-label",
      "QazaqPlay 3D әлемі. Жерді басып қозғалыңыз немесе WASD пернелерін қолданыңыз.",
    );
    this.renderer.domElement.style.touchAction = "none";
    host.appendChild(this.renderer.domElement);
    const options = { signal: this.listeners.signal };
    window.addEventListener("keydown", this.onKeyDown, options);
    window.addEventListener("keyup", this.onKeyUp, options);
    window.addEventListener("blur", this.clearInput, options);
    document.addEventListener("visibilitychange", this.visibility, options);
    this.renderer.domElement.addEventListener(
      "pointerdown",
      this.pointerDown,
      options,
    );
    this.renderer.domElement.addEventListener(
      "pointerup",
      this.pointerUp,
      options,
    );
    this.renderer.domElement.addEventListener(
      "webglcontextlost",
      this.contextLost,
      options,
    );
    this.observer = new ResizeObserver(this.resize);
    this.observer.observe(host);
    this.setQuality(quality);
    this.resize();
    this.schedule();
  }

  private contextLost = (event: Event) => {
    event.preventDefault();
    this.setPaused(true);
    this.events.error();
  };
  private clearInput = () => {
    this.keys.clear();
    this.joystick = { x: 0, y: 0 };
    this.destination = null;
    this.route = [];
  };
  private onKeyDown = (event: KeyboardEvent) => {
    if (
      !this.playing ||
      this.paused ||
      /INPUT|TEXTAREA|BUTTON|SELECT/.test(
        (event.target as HTMLElement)?.tagName ?? "",
      )
    )
      return;
    if (
      [
        "KeyW",
        "KeyA",
        "KeyS",
        "KeyD",
        "ArrowUp",
        "ArrowDown",
        "ArrowLeft",
        "ArrowRight",
      ].includes(event.code)
    ) {
      event.preventDefault();
      this.keys.add(event.code);
      this.destination = null;
      this.route = [];
    }
    if ((event.code === "Space" || event.code === "KeyE") && !event.repeat) {
      event.preventDefault();
      this.events.interact();
    }
  };
  private onKeyUp = (event: KeyboardEvent) => {
    this.keys.delete(event.code);
  };
  private pointerDown = (event: PointerEvent) => {
    this.pointer = { x: event.clientX, y: event.clientY };
  };
  private pointerUp = (event: PointerEvent) => {
    if (
      !this.playing ||
      this.paused ||
      !this.pointer ||
      Math.hypot(
        this.pointer.x - event.clientX,
        this.pointer.y - event.clientY,
      ) > 12
    )
      return;
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.raycaster.setFromCamera(
      new THREE.Vector2(
        ((event.clientX - rect.left) / rect.width) * 2 - 1,
        (-(event.clientY - rect.top) / rect.height) * 2 + 1,
      ),
      this.camera,
    );
    const hit = this.raycaster.intersectObject(this.world.ground)[0];
    if (hit && Math.hypot(hit.point.x, hit.point.z) < 20.7) {
      this.navigate(hit.point);
      this.keys.clear();
    }
    this.pointer = null;
  };
  private visibility = () => {
    this.clearInput();
    if (document.hidden) {
      cancelAnimationFrame(this.frame);
      this.frame = 0;
    } else {
      this.last = 0;
      this.schedule();
    }
  };
  private resize = () => {
    if (this.disposed) return;
    const width = this.host.clientWidth,
      height = this.host.clientHeight;
    if (!width || !height) return;
    this.renderer.setSize(width, height, false);
    const halfHeight = this.playing
      ? width < 700
        ? 16
        : 13
      : width < 700
        ? 30
        : 25;
    const aspect = width / height;
    Object.assign(this.camera, {
      left: -halfHeight * aspect,
      right: halfHeight * aspect,
      top: halfHeight,
      bottom: -halfHeight,
    });
    this.camera.updateProjectionMatrix();
    this.render();
  };
  private schedule() {
    if (!this.frame && !this.disposed && !this.paused && !document.hidden)
      this.frame = requestAnimationFrame(this.tick);
  }
  private tick = (stamp: number) => {
    this.frame = 0;
    if (this.disposed || this.paused || document.hidden) return;
    const interval = 1000 / (this.quality === "low" ? 30 : 45);
    if (this.last && stamp - this.last < interval - 1) {
      this.schedule();
      return;
    }
    const dt = this.last ? Math.min((stamp - this.last) / 1000, 0.05) : 0;
    this.last = stamp;
    this.time += dt;
    let moving = false;
    if (this.playing) moving = this.updateMovement(dt);
    this.world.animate(this.time, dt, moving);
    const desired = this.playing
      ? this.world.hero.position
      : new THREE.Vector3(-8, 0, 1);
    this.focus.lerp(desired, Math.min(1, dt * 5));
    this.render();
    this.schedule();
  };
  private render() {
    this.camera.position.copy(this.focus).add(this.offset);
    this.camera.lookAt(this.focus.x, 0, this.focus.z);
    this.renderer.render(this.world.scene, this.camera);
  }
  private allowed(x: number, z: number) {
    return canWalk({ x, z }, this.world.obstacles);
  }
  private updateMovement(dt: number): boolean {
    let x = this.joystick.x,
      y = this.joystick.y;
    if (this.keys.has("KeyA") || this.keys.has("ArrowLeft")) x -= 1;
    if (this.keys.has("KeyD") || this.keys.has("ArrowRight")) x += 1;
    if (this.keys.has("KeyW") || this.keys.has("ArrowUp")) y -= 1;
    if (this.keys.has("KeyS") || this.keys.has("ArrowDown")) y += 1;
    const position = this.world.hero.position;
    this.move.set((x + y) * Math.SQRT1_2, 0, (y - x) * Math.SQRT1_2);
    if (this.destination) {
      this.move.subVectors(this.destination, position).setY(0);
      if (this.move.length() < 0.15) {
        const next = this.route.shift();
        this.destination = next ? new THREE.Vector3(next.x, 0, next.z) : null;
        this.move.set(0, 0, 0);
      }
    }
    const moving = this.move.lengthSq() > 0.01;
    if (moving) {
      this.move.normalize().multiplyScalar(dt * 5.3);
      if (this.allowed(position.x + this.move.x, position.z))
        position.x += this.move.x;
      if (this.allowed(position.x, position.z + this.move.z))
        position.z += this.move.z;
      this.world.hero.rotation.y = Math.atan2(this.move.x, this.move.z);
    }
    this.world.destination.visible = this.destination !== null;
    if (this.destination)
      this.world.destination.position.set(
        this.destination.x,
        0.16,
        this.destination.z,
      );
    const nearest =
      TARGETS.find(
        (target) =>
          Math.hypot(target.x - position.x, target.z - position.z) < 2.8,
      ) ?? null;
    if ((nearest?.id ?? "") !== this.nearId) {
      this.nearId = nearest?.id ?? "";
      this.events.near(nearest);
    }
    return moving;
  }
  setJoystick(x: number, y: number) {
    this.joystick = { x, y };
    if (x || y) {
      this.destination = null;
      this.route = [];
    }
  }
  setPlaying(playing: boolean) {
    this.playing = playing;
    this.clearInput();
    this.resize();
  }
  setPaused(paused: boolean) {
    this.paused = paused;
    this.clearInput();
    cancelAnimationFrame(this.frame);
    this.frame = 0;
    if (!paused) {
      this.last = 0;
      this.schedule();
    }
  }
  setQuality(quality: Quality) {
    this.quality = quality;
    this.world.terrain.setQuality(quality);
    this.renderer.setPixelRatio(
      Math.min(window.devicePixelRatio || 1, quality === "low" ? 1 : 1.5),
    );
    this.renderer.shadowMap.enabled = quality === "high";
    this.world.scene.traverse((object) => {
      if (
        object instanceof THREE.Mesh &&
        object.material instanceof THREE.Material
      )
        object.material.needsUpdate = true;
    });
    this.resize();
  }
  setProgress(progress: Progress) {
    this.world.progress(progress);
    this.render();
  }
  goTo(target: WorldTarget) {
    this.navigate({ x: target.x, z: target.z + 1.9 });
  }
  private navigate(target: Point) {
    this.route = findPath(
      this.world.hero.position,
      target,
      this.world.obstacles,
    );
    const first = this.route.shift();
    this.destination = first ? new THREE.Vector3(first.x, 0, first.z) : null;
  }
  home() {
    this.clearInput();
    this.world.hero.position.set(0, 0, 5);
  }
  cast() {
    this.world.cast();
  }
  dispose() {
    this.disposed = true;
    cancelAnimationFrame(this.frame);
    this.listeners.abort();
    this.observer.disconnect();
    this.world.dispose();
    this.renderer.dispose();
    this.renderer.forceContextLoss();
    this.renderer.domElement.remove();
  }
}
