// Ручная проверка чека может пережить закрытие Mini App и обычный срок памяти экрана.
const KEY_PREFIX = "qc_payment_return:";
export const PAYMENT_RETURN_TTL_MS = 7 * 24 * 60 * 60 * 1000;

export interface PaymentReturn {
  movieId: number | null; // null — оплату открыли из профиля
}

export function savePaymentReturn(telegramId: number, target: PaymentReturn): void {
  try {
    localStorage.setItem(KEY_PREFIX + telegramId, JSON.stringify({ ...target, savedAt: Date.now() }));
  } catch {
    /* Закрытое хранилище не должно мешать оплате. */
  }
}

export function loadPaymentReturn(telegramId: number): PaymentReturn | null {
  try {
    const now = Date.now();
    const stored = JSON.parse(localStorage.getItem(KEY_PREFIX + telegramId) ?? "null") as {
      movieId?: number | null;
      savedAt?: number;
    } | null;
    if (
      stored &&
      typeof stored.savedAt === "number" &&
      stored.savedAt <= now &&
      now - stored.savedAt <= PAYMENT_RETURN_TTL_MS &&
      (stored.movieId === null ||
        (typeof stored.movieId === "number" &&
          Number.isSafeInteger(stored.movieId) &&
          stored.movieId > 0))
    ) {
      return { movieId: stored.movieId };
    }
  } catch {
    /* Сломанная память о выборе не должна мешать входу. */
  }
  return null;
}

export function clearPaymentReturn(telegramId: number): void {
  try {
    localStorage.removeItem(KEY_PREFIX + telegramId);
  } catch {
    /* Хранилище может быть недоступно. */
  }
}
