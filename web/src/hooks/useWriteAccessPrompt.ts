// Право боту писать в личку — просим САМИ, на входе, нативным попапом Telegram.
//
// Без этого права кинотеатр для человека не работает вообще: фильм уходит сообщением, а
// первым бот писать не вправе. Раньше единственной дорогой был поход в чат за кнопкой
// START — и по живым данным на нём останавливались 34 человека из 123, ни один из
// которых не посмотрел ни одного фильма. Попап решает то же самое одним нажатием, не
// сворачивая приложение.

import { useEffect, useRef } from "react";

import { api, type Auth } from "../lib/api";
import { haptic, requestWriteAccess } from "../lib/telegram";

// Пауза перед попапом. Нужна, чтобы человек успел увидеть, КУДА он попал: системный
// запрос поверх голого скелета выглядит как требование неизвестно от кого, и его
// закрывают не читая. Полсекунды — главная уже отрисована, приложение ещё не пролистано.
const PROMPT_DELAY_MS = 600;

/**
 * Спросить право один раз за заход, пока `active`.
 *
 * Один раз — через ref, а не state: перерисовка не должна открывать попап заново. Отказ
 * и старый клиент оставляют всё как было: шторка `BotStartSheet` с дорогой в чат никуда
 * не делась и покажется на «Көру».
 */
export function useWriteAccessPrompt(
  active: boolean,
  setAuth: React.Dispatch<React.SetStateAction<Auth | null>>,
): void {
  const asked = useRef(false);
  useEffect(() => {
    if (!active || asked.current) return;
    asked.current = true;
    const timer = setTimeout(() => {
      void (async () => {
        if (!(await requestWriteAccess())) return;
        haptic.success();
        try {
          setAuth(await api.grantWriteAccess());
        } catch {
          // Сеть моргнула на записи факта — состояние всё равно поднимаем: отправка
          // видео от признака не зависит, а успешная доставка чинит флаг на бэке сама
          // (`PlaybackService` проставляет его при первой же удачной выдаче).
          setAuth((prev) => (prev ? { ...prev, bot_started: true } : prev));
        }
      })();
    }, PROMPT_DELAY_MS);
    return () => clearTimeout(timer);
  }, [active, setAuth]);
}
