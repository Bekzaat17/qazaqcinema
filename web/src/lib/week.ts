// Счётчик недельного окна выбора. Окно ОБЩЕЕ для всех (понедельник 00:00 по Алматы),
// поэтому фронт не считает срок по каждому юзеру — бэк отдаёт один `week_ends_at`
// в `/api/auth` и `/api/me`, а здесь он превращается в текст.
//
// Считаем в ЦЕЛЫХ днях вверх: «1 күн қалды» в последние сутки честнее, чем «0 күн».
// Округление вниз показывало бы ноль почти целые сутки — человек решил бы, что окно
// уже закрыто, и не стал бы забирать то, что ему ещё положено.

/** Сколько суток осталось до конца окна; 0 — окно уже закрыто (или срока нет). */
export function daysLeft(weekEndsAt: string | null | undefined, now = Date.now()): number {
  if (!weekEndsAt) return 0;
  const ms = new Date(weekEndsAt).getTime() - now;
  if (!Number.isFinite(ms) || ms <= 0) return 0;
  return Math.ceil(ms / 86_400_000);
}

/** Подпись для бейджа и строки профиля: «3 күн қалды». Пусто — если срока нет. */
export function weekLeftLabel(weekEndsAt: string | null | undefined, now = Date.now()): string {
  const left = daysLeft(weekEndsAt, now);
  return left > 0 ? `${left} күн қалды` : "";
}

/** Дата закрытия окна для шторки подтверждения: «28 қыркүйекке дейін». */
const MONTHS_KK = [
  "қаңтар", "ақпан", "наурыз", "сәуір", "мамыр", "маусым",
  "шілде", "тамыз", "қыркүйек", "қазан", "қараша", "желтоқсан",
];

export function untilLabel(weekEndsAt: string | null | undefined): string {
  if (!weekEndsAt) return "";
  const end = new Date(weekEndsAt);
  if (Number.isNaN(end.getTime())) return "";
  // Окно закрывается в понедельник 00:00, то есть последний доступный день — воскресенье.
  // Называть человеку понедельник значило бы обещать сутки, которых у него нет.
  const last = new Date(end.getTime() - 86_400_000);
  return `${last.getDate()} ${MONTHS_KK[last.getMonth()]}`;
}
