// Типизация нужных нам частей Telegram WebApp SDK (расширяем по мере надобности).
export {};

interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  language_code?: string;
  photo_url?: string;
}

interface HapticFeedback {
  impactOccurred(style: "light" | "medium" | "heavy" | "rigid" | "soft"): void;
  notificationOccurred(type: "error" | "success" | "warning"): void;
  selectionChanged(): void;
}

interface BottomButton {
  text: string;
  isVisible: boolean;
  isActive: boolean;
  setText(text: string): BottomButton;
  onClick(cb: () => void): BottomButton;
  offClick(cb: () => void): BottomButton;
  show(): BottomButton;
  hide(): BottomButton;
  enable(): BottomButton;
  disable(): BottomButton;
  showProgress(leaveActive?: boolean): BottomButton;
  hideProgress(): BottomButton;
  setParams(params: {
    text?: string;
    color?: string;
    text_color?: string;
    is_active?: boolean;
    is_visible?: boolean;
  }): BottomButton;
}

interface BackButton {
  isVisible: boolean;
  onClick(cb: () => void): BackButton;
  offClick(cb: () => void): BackButton;
  show(): BackButton;
  hide(): BackButton;
}

type InvoiceStatus = "paid" | "cancelled" | "failed" | "pending";

interface TelegramWebApp {
  initData: string;
  initDataUnsafe: { user?: TelegramUser };
  version: string;
  platform: string;
  colorScheme: "light" | "dark";
  viewportHeight: number;
  viewportStableHeight: number;
  isExpanded: boolean;

  ready(): void;
  expand(): void;
  close(): void;
  switchInlineQuery(query: string, chooseChatTypes?: string[]): void;
  openInvoice(url: string, callback?: (status: InvoiceStatus) => void): void;
  openTelegramLink(url: string): void;
  openLink(url: string, options?: { try_instant_view?: boolean }): void;
  showAlert(message: string, callback?: () => void): void;
  showConfirm(message: string, callback?: (ok: boolean) => void): void;
  setHeaderColor(color: string): void;
  setBackgroundColor(color: string): void;
  disableVerticalSwipes?(): void;

  HapticFeedback: HapticFeedback;
  MainButton: BottomButton;
  BackButton: BackButton;
}

interface TelegramNamespace {
  WebApp: TelegramWebApp;
}

declare global {
  interface Window {
    Telegram?: TelegramNamespace;
  }
}
