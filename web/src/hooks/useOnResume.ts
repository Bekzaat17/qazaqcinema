// «Приложение снова на экране» — один хук на всех, кому важен возврат.
//
// Mini App живёт короткими заходами: человек уходит в чат с ботом за видео, сворачивает
// Telegram, возвращается. Ровно в этот момент устаревает всё, что мы загрузили на входе:
// статус подписки (решение админа приходит извне), каталог (админ залил новинку), сама
// сборка приложения. Все три проверки слушали одну и ту же пару событий каждая своей
// копией — теперь пара живёт здесь.

import { useEffect } from "react";

/**
 * Позвать `onResume`, когда приложение снова видно.
 *
 * Слушаем и `visibilitychange`, и `focus`: какое из них придёт при возврате, зависит от
 * клиента Telegram, а лишний вызов безвреден — вызывающие либо идемпотентны, либо со
 * своим троттлингом. Обработчик срабатывает только на ВИДИМОЙ странице, иначе
 * `visibilitychange` дёргал бы его и в момент сворачивания.
 *
 * `onResume` должен быть стабильным (`useCallback`) — иначе подписка пересоздаётся
 * на каждый рендер.
 */
export function useOnResume(enabled: boolean, onResume: () => void): void {
  useEffect(() => {
    if (!enabled) return;
    const handler = () => {
      if (!document.hidden) onResume();
    };
    document.addEventListener("visibilitychange", handler);
    window.addEventListener("focus", handler);
    return () => {
      document.removeEventListener("visibilitychange", handler);
      window.removeEventListener("focus", handler);
    };
  }, [enabled, onResume]);
}
