// Подписи категорий (kk). Раскладку полок главной теперь собирает бэкенд (Фаза 13),
// а страницы каталога отдаёт `/api/movies` — на фронте осталась только локализация.

/** Подписи категорий (зеркало domain/catalog/categories.py, основной язык — казахский). */
const CATEGORY_LABELS: Record<string, string> = {
  disney: "Мультфильмдер",
  anime: "Аниме",
  film: "Фильмдер",
  serial: "Сериалдар",
  short: "Қысқа метр",
  otandyq: "Отандық",
  kids: "Балаларға",
  girls: "Қыздарға",
  boys: "Ұлдарға",
  family: "Отбасылық",
  adventure: "Шытырман оқиға",
  comedy: "Күлкілі",
  fantasy: "Қиял-ғажайып",
  fairytale: "Ертегілер",
  learning: "Білім беру",
  classic: "Классика",
};

export function categoryLabel(slug: string): string {
  return CATEGORY_LABELS[slug] ?? slug.charAt(0).toUpperCase() + slug.slice(1);
}
