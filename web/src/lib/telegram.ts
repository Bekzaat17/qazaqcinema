// Тонкая обёртка над Telegram WebApp SDK. Всё опционально: вне Telegram (dev в браузере)
// методы — no-op, чтобы приложение оставалось рабочим для отладки вёрстки.

/**
 * @-имя бота — единственное место, где оно зашито на фронте (должно совпадать с
 * `BOT_USERNAME` бэкенда). Нужно гостю, пришедшему из поиска в обычный браузер: ему
 * показывают не каталог, а дорогу в Telegram — и она должна быть кликабельной ссылкой.
 */
export const BOT_USERNAME: string = import.meta.env.VITE_BOT_USERNAME || "qazaqcinema_bot";
export const BOT_URL = `https://t.me/${BOT_USERNAME}`;

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
 * ID фильма, на котором открыть кинотеатр. Источники по приоритету:
 *  • `?m=<id>` — кнопка бота в ответ на ссылку из канала/с сайта (`movie_keyboard`);
 *  • `start_param` — старая прямая ссылка `t.me/<bot>?startapp=[<источник>-]m_<id>`;
 *  • хэш `#m<id>` — ещё более старый фолбэк. Telegram дописывает в хэш свои параметры
 *    (`#m42&tgWebAppData=…`), поэтому берём только часть до первого `&`.
 */
export function getStartMovieId(): number | null {
  const fromQuery = /^\d+$/.exec(new URLSearchParams(window.location.search).get("m") ?? "");
  if (fromQuery) return Number(fromQuery[0]);
  const raw =
    window.Telegram?.WebApp?.initDataUnsafe?.start_param ??
    window.location.hash.slice(1).split("&")[0];
  const match = /^(?:[a-z]{1,16}-)?m_?(\d+)$/.exec(raw ?? "");
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
  setVerticalSwipes(false); // чтобы свайпы внутри полок не сворачивали Mini App
}

/**
 * Вертикальный свайп: закрывает ли он Mini App.
 *
 * По умолчанию выключен на весь каталог — иначе протяжка полки норовит свернуть
 * приложение. Включать обратно есть смысл там, где выход и есть цель экрана
 * (`HandoffModal`): это единственный ручной выход, который не зависит от того,
 * послушался ли клиент наших методов.
 */
export function setVerticalSwipes(enabled: boolean): void {
  const wa = getWebApp();
  if (enabled) wa?.enableVerticalSwipes?.();
  else wa?.disableVerticalSwipes?.();
}

/** Платформа клиента (`ios`, `android`, `tdesktop`, `weba`…) — для разбивки метрик. */
export function getPlatform(): string {
  const raw = getWebApp()?.platform ?? "";
  // Значение уходит в журнал событий, где формат сужен схемой ручки: чистим здесь,
  // чтобы диагностика не терялась на 422 из-за неожиданной строки в новом клиенте.
  return raw.toLowerCase().replace(/[^a-z0-9_]/g, "").slice(0, 16) || "unknown";
}

/**
 * Запущено ли приложение прямой ссылкой (`t.me/<bot>?startapp=…`) — из браузера, поиска
 * или кнопки в канале. Отличие принципиальное: под таким запуском НЕТ чата с ботом, и
 * закрытие Mini App вернёт человека туда, откуда он пришёл, а не к видео.
 */
export function isDirectLaunch(): boolean {
  return Boolean(getWebApp()?.initDataUnsafe?.start_param);
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

/**
 * Открыть t.me-ссылку ВНУТРИ Telegram (канал, чат): Mini App сворачивается, сверху встаёт
 * нужный экран. Именно `openTelegramLink`, а не `openLink` — последний уводит t.me во
 * внешний браузер, где человек видит веб-превью канала с кнопкой «Open in Telegram»
 * вместо самого канала, на который мы его и просим подписаться.
 */
export function openTelegramLink(url: string): void {
  const wa = getWebApp();
  if (wa?.openTelegramLink) wa.openTelegramLink(url);
  else openLink(url);
}

/**
 * Открыть чат с ботом ВНУТРИ Telegram (Mini App сворачивается, сверху встаёт чат).
 * Именно `openTelegramLink`, а не `openLink`: последний уводит t.me во внешний браузер,
 * и человек оказывался бы на веб-странице вместо чата, который ему как раз и нужен.
 *
 * `payload` — ТОЛЬКО для случая, когда чата с ботом ещё не было (`BotStartSheet`): без него
 * человек, впервые тыкающий на ссылку, просто открывает пустой чат. С параметром — Telegram
 * рисует большую кнопку START, а нажатие шлёт `/start <payload>`.
 * ⚠️ НЕ звать с `payload` там, где переписка с ботом уже идёт: Telegram шлёт
 * `/start <payload>` заново при КАЖДОМ переходе по такой ссылке, и вместо нужного
 * сообщения человек получает дефолтное приветствие `GREETING` (`handlers/start.py`),
 * затирающее контекст. Без `payload` метод открывает существующий чат как есть.
 */
export function openBotChat(payload?: string): void {
  openTelegramLink(payload ? `${BOT_URL}?start=${payload}` : BOT_URL);
}

/**
 * Закрыть Mini App — так человек уходит в чат с ботом, где лежит отправленное видео.
 *
 * Работает ТОЛЬКО у запуска из чата (кнопка меню, клавиатура бота): под приложением тот
 * самый чат, и достаточно закрыться. У прямой ссылки (сайт, пост канала) под нами канал
 * или браузер, а открыть чат своего же бота клиент не даёт: `openTelegramLink` на него
 * молча игнорируется — и с паузой перед `close()`, и без неё (проверено на телефоне).
 * Закрытие там возвращает человека в канал, а не к видео, поэтому `HandoffModal` при
 * прямом запуске сюда не ходит, а объясняет дорогу словами.
 *
 * ⚠️ `close()` — сообщение по мосту без ответа и без ошибки: часть клиентов его молча
 * игнорирует. Тот, кто зовёт, обязан предусмотреть ручной выход (`HandoffModal`).
 */
export function closeApp(): void {
  getWebApp()?.close();
}

/** Как запущено приложение — для разбивки метрик хэндоффа (см. `HandoffModal`). */
export function getLaunch(): "direct" | "chat" {
  return isDirectLaunch() ? "direct" : "chat";
}

/**
 * Попросить у человека право боту писать ему в личку — нативным попапом Telegram.
 *
 * Это короткий путь к тому же, ради чего раньше гоняли в чат за кнопкой START: фильм
 * уходит сообщением, и Telegram пускает его только с разрешения. Попап показывается
 * поверх Mini App, ответ приходит одним нажатием, приложение не сворачивается.
 *
 * Возвращает false и в отказе, и в старом клиенте без метода — на оба случая у нас один
 * ответ: остаётся прежняя шторка `BotStartSheet` с дорогой в чат.
 */
export function requestWriteAccess(): Promise<boolean> {
  return new Promise((resolve) => {
    const wa = getWebApp();
    if (!wa?.requestWriteAccess) {
      resolve(false);
      return;
    }
    try {
      wa.requestWriteAccess((granted) => resolve(granted));
    } catch {
      // Метод объявлен, но клиент старее нужной версии — Telegram бросает синхронно.
      resolve(false);
    }
  });
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
