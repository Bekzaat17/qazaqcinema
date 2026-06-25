// Минимальная типизация Telegram WebApp SDK. Расширяется по мере надобности (PLAN).
export {};

interface TelegramWebApp {
  initData: string;
  ready(): void;
  expand(): void;
  close(): void;
  switchInlineQuery(query: string, chooseChatTypes?: string[]): void;
}

interface TelegramNamespace {
  WebApp: TelegramWebApp;
}

declare global {
  interface Window {
    Telegram?: TelegramNamespace;
  }
}
