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

/**
 * «Играть отсюда»: трек и всё, что после него, — так список уходит в чат, и Telegram
 * играет его дальше по порядку. Не больше `limit` за раз.
 */
export function fromHere<T>(items: readonly T[], index: number, limit: number): T[] {
  return items.slice(Math.max(0, index), Math.max(0, index) + limit);
}

/** Сдвинуть элемент на соседнюю позицию (режим «Реттеу»); за краями — без изменений. */
export function moved<T>(items: readonly T[], index: number, step: -1 | 1): T[] {
  const target = index + step;
  if (index < 0 || index >= items.length || target < 0 || target >= items.length) return [...items];
  const next = [...items];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}
