// Мелкие форматтеры музыки — чистые функции (тестируются без DOM).

export function duration(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = String(total % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}

/** «12 ән» — в казахском число не меняет форму существительного. */
export function tracksLabel(count: number): string {
  return `${count} ән`;
}

/** Цвета обложки-заглушки из названия: у одного трека всегда одна и та же. */
export function coverGradient(seed: string): string {
  let hash = 0;
  for (const char of seed) hash = (hash * 31 + char.charCodeAt(0)) | 0;
  const hue = Math.abs(hash) % 360;
  const second = (hue + 48) % 360;
  return `linear-gradient(135deg, hsl(${hue} 70% 46%), hsl(${second} 75% 30%))`;
}

export function initials(text: string): string {
  const letters = text
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? "");
  return letters.join("") || "♪";
}

/** Следующий индекс очереди с учётом повтора; null — очередь кончилась. */
export function nextIndex(index: number, length: number, repeat: "off" | "all" | "one"): number | null {
  if (length === 0) return null;
  if (repeat === "one") return index;
  if (index + 1 < length) return index + 1;
  return repeat === "all" ? 0 : null;
}

/**
 * Следующий трек при АВТОпереходе: тяжёлые треки (только в Telegram) пропускаются —
 * иначе музыка молча вставала бы посреди плейлиста. Ручное «Келесі» их не пропускает.
 */
export function nextPlayable(
  queue: readonly { stream_url: string | null }[],
  index: number,
  repeat: "off" | "all" | "one",
): number | null {
  let candidate = nextIndex(index, queue.length, repeat);
  for (let tries = 0; candidate !== null && tries < queue.length; tries++) {
    if (queue[candidate].stream_url) return candidate;
    candidate = nextIndex(candidate, queue.length, repeat === "one" ? "off" : repeat);
  }
  return null;
}

/** Перемешать очередь, оставив текущий трек первым (Фишер — Йейтс). */
export function shuffled<T>(items: readonly T[], current: number, random: () => number = Math.random): T[] {
  if (items.length === 0) return [];
  const rest = items.filter((_, index) => index !== current);
  for (let i = rest.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [rest[i], rest[j]] = [rest[j], rest[i]];
  }
  return [items[current], ...rest];
}
