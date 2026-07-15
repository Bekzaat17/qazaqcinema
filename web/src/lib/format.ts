// Форматирование для казахского UI.

/** Цена в тенге с пробелом-разделителем тысяч: 1290 → «1 290 ₸». */
export function tenge(amount: number): string {
  return `${amount.toLocaleString("ru-RU").replace(/,/g, " ")} ₸`;
}

/** Цена за сутки для месячного тарифа: «63 ₸/күн». */
export function perDay(priceKzt: number, days: number): string {
  return `${Math.round(priceKzt / days)} ₸/күн`;
}

/** Сколько дней осталось до даты (ISO). Не меньше нуля. */
export function daysLeft(expiresAt: string | null): number {
  if (!expiresAt) return 0;
  const ms = new Date(expiresAt).getTime() - Date.now();
  return Math.max(0, Math.ceil(ms / 86_400_000));
}

// Названия месяцев вручную: Intl-данные kk-KZ есть не во всех webview (Telegram отдаёт «M07»).
const MONTHS_KK = [
  "қаңтар", "ақпан", "наурыз", "сәуір", "мамыр", "маусым",
  "шілде", "тамыз", "қыркүйек", "қазан", "қараша", "желтоқсан",
];

/** Дата окончания в казахском формате: «22 шілде 2026». */
export function formatDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return `${d.getDate()} ${MONTHS_KK[d.getMonth()]} ${d.getFullYear()}`;
}

/** Инициалы для аватара-заглушки. */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p[0]?.toUpperCase() ?? "").join("") || "?";
}
