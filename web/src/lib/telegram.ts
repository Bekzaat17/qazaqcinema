// Тонкая обёртка над Telegram WebApp SDK. Всё опционально: вне Telegram (dev в браузере)
// методы — no-op, чтобы приложение оставалось рабочим для отладки вёрстки.

export function getWebApp() {
  return window.Telegram?.WebApp;
}

export function getInitData(): string {
  return window.Telegram?.WebApp?.initData ?? "";
}

export function getTelegramUser() {
  return window.Telegram?.WebApp?.initDataUnsafe?.user;
}

/**
 * ID фильма из deep-link (SEO-страница → «Telegram-да көру»). Источники по приоритету:
 * `start_param` Mini App (t.me/<bot>?startapp=m_<id>) → хэш URL (#m<id>, фолбэк для /start).
 * Возвращает число или null. Формат payload: `m_<id>` либо `m<id>`.
 */
export function getStartMovieId(): number | null {
  const raw =
    window.Telegram?.WebApp?.initDataUnsafe?.start_param ??
    (window.location.hash ? window.location.hash.slice(1) : "");
  const match = /^m_?(\d+)$/.exec(raw ?? "");
  return match ? Number(match[1]) : null;
}

/** Стартовая инициализация: готовность, разворот на весь экран, брендовые цвета шапки/фона. */
export function initWebApp(): void {
  const wa = getWebApp();
  if (!wa) return;
  wa.ready();
  wa.expand();
  wa.setHeaderColor("#09090b");
  wa.setBackgroundColor("#09090b");
  wa.disableVerticalSwipes?.(); // чтобы свайпы внутри полок не сворачивали Mini App
}

export function close(): void {
  getWebApp()?.close();
}

// ── Тактильная отдача ──
export const haptic = {
  light: () => getWebApp()?.HapticFeedback?.impactOccurred("light"),
  medium: () => getWebApp()?.HapticFeedback?.impactOccurred("medium"),
  rigid: () => getWebApp()?.HapticFeedback?.impactOccurred("rigid"),
  success: () => getWebApp()?.HapticFeedback?.notificationOccurred("success"),
  warning: () => getWebApp()?.HapticFeedback?.notificationOccurred("warning"),
  error: () => getWebApp()?.HapticFeedback?.notificationOccurred("error"),
  select: () => getWebApp()?.HapticFeedback?.selectionChanged(),
};

// ── Нативная кнопка «назад» в шапке Telegram ──
export function showBackButton(onClick: () => void): () => void {
  const wa = getWebApp();
  const back = wa?.BackButton;
  if (!back) return () => {};
  back.onClick(onClick);
  back.show();
  // возвращаем «отписку»: снять обработчик и спрятать кнопку
  return () => {
    back.offClick(onClick);
    back.hide();
  };
}

/** Открыть внешнюю ссылку (напр. Kaspi Pay) вне Mini App. Вне Telegram — обычный переход. */
export function openLink(url: string): void {
  const wa = getWebApp();
  if (wa?.openLink) {
    wa.openLink(url);
  } else {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}

/** Открыть инвойс Telegram Stars. Резолвится статусом оплаты. */
export function openInvoice(url: string): Promise<string> {
  return new Promise((resolve) => {
    const wa = getWebApp();
    if (!wa?.openInvoice) {
      resolve("failed");
      return;
    }
    wa.openInvoice(url, (status) => resolve(status));
  });
}
