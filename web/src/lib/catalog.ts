// Каталожная логика фронта: подписи категорий (kk) и раскладка главного экрана на полки.

import type { Movie } from "./api";

/** Подписи категорий (зеркало domain/catalog/categories.py, основной язык — казахский). */
const CATEGORY_LABELS: Record<string, string> = {
  disney: "Мультфильмдер",
  anime: "Аниме",
  film: "Фильмдер",
  serial: "Сериалдар",
  otandyq: "Отандық",
  kids: "Балаларға",
};

export function categoryLabel(slug: string): string {
  return CATEGORY_LABELS[slug] ?? slug.charAt(0).toUpperCase() + slug.slice(1);
}

export interface Shelf {
  key: string;
  title: string;
  movies: Movie[];
}

// Категорийный ряд показываем только если в нём достаточно тайтлов — иначе на маленьком
// каталоге одни и те же фильмы дублируются в нескольких рядах (см. PLAN, Фаза 9).
const MIN_CATEGORY_ROW = 3;

/** «Новизна» — по убыванию id (id автоинкрементный, так что больший id = свежее). */
function byNewest(a: Movie, b: Movie): number {
  return b.id - a.id;
}

/** Раскладывает каталог на полки. Hero выбирает бэкенд (`/api/movies/hero`) — здесь мы
 * лишь исключаем его из «Жаңа түскен», чтобы он не дублировался под своим же баннером. */
export function buildShelves(movies: Movie[], heroId?: number): { shelves: Shelf[] } {
  if (movies.length === 0) return { shelves: [] };

  const sorted = [...movies].sort(byNewest);
  const shelves: Shelf[] = [];

  // «Жаңа түскен» — всё, кроме hero (он уже наверху крупно).
  const fresh = sorted.filter((m) => m.id !== heroId);
  if (fresh.length > 0) {
    shelves.push({ key: "fresh", title: "Жаңа түскен", movies: fresh });
  }

  // Ряды по категориям — в порядке первого появления, только при достаточном размере.
  const seen = new Set<string>();
  for (const movie of sorted) {
    if (seen.has(movie.category)) continue;
    seen.add(movie.category);
    const inCategory = sorted.filter((m) => m.category === movie.category);
    if (inCategory.length >= MIN_CATEGORY_ROW) {
      shelves.push({ key: `cat:${movie.category}`, title: categoryLabel(movie.category), movies: inCategory });
    }
  }

  return { shelves };
}
