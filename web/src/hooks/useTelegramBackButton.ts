// Показывает нативную кнопку «назад» Telegram, пока active=true, и зовёт onBack по нажатию.
// Единственная точка управления кнопкой — вызывается в App поверх всего стека оверлеев,
// чтобы не плодить конкурирующие обработчики (BackButton в Telegram один на весь Mini App).

import { useEffect } from "react";

import { showBackButton } from "../lib/telegram";

export function useTelegramBackButton(active: boolean, onBack: () => void): void {
  useEffect(() => {
    if (!active) return;
    return showBackButton(onBack);
  }, [active, onBack]);
}
