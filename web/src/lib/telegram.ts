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
  const url = payload ? `${BOT_URL}?start=${payload}` : BOT_URL;
  const wa = getWebApp();
  if (wa?.openTelegramLink) wa.openTelegramLink(url);
  else openLink(url);
}

/**
 * Увести человека из Mini App в чат с ботом, где лежит только что отправленное видео.
 *
 * Дорога зависит от того, что находится ПОД приложением. Запуск из чата (кнопка меню,
 * клавиатура бота) — под нами тот самый чат, и достаточно закрыться. Прямая ссылка —
 * под нами браузер или поиск, поэтому чат сначала надо открыть явно; закрытие после
 * этого убирает наше окно с дороги (с Bot API 7.0 `openTelegramLink` сам его не гасит).
 *
 * ⚠️ Оба метода — сообщения по мосту без ответа и без ошибки: часть клиентов их молча
 * игнорирует. Считать вызов состоявшимся нельзя — тот, кто зовёт, обязан предусмотреть
 * ручной выход, если через секунду мы всё ещё на экране (`HandoffModal`).
 */
export function leaveToChat(): void {
  if (isDirectLaunch()) openBotChat();
  getWebApp()?.close();
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
