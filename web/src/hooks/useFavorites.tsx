// Избранное («Таңдаулы») — общее состояние на всё приложение.
//
// Контекст, а не пропсы: звезда нужна постеру, который лежит в глубине трёх разных
// деревьев (полки главной, сетка каталога, выдача поиска, сама вкладка избранного).
// Тащить туда `ids` и `onToggle` пришлось бы через каждый промежуточный компонент,
// который к избранному никакого отношения не имеет.
//
// Тумблер ОПТИМИСТИЧНЫЙ: звезда закрашивается сразу, запрос уходит следом. Мобильная
// сеть легко даёт секунду задержки, а тап по звезде — жест, который обязан откликаться
// мгновенно. Расхождение с сервером чиним перезагрузкой списка (сервер — источник правды).
//
// ⚠️ Два правила, без которых серия быстрых тапов ломается (и уже ломала):
//
//   1. Решение «ставим или снимаем» берётся из РЕФА, а не из состояния и не изнутри
//      updater'а `setState`. React вызывает updater отложенно (на этапе рендера), поэтому
//      прочитать его результат сразу после вызова нельзя: при быстрых тапах вторая и
//      последующие звёзды видели устаревшее «ещё не добавлено» и отправляли на сервер
//      DELETE вместо PUT. Локально звезда закрашивалась, а на сервере фильма не было —
//      во вкладке он потом не появлялся.
//   2. Запросы по ОДНОМУ фильму выстраиваются в цепочку. PUT и DELETE, ушедшие
//      параллельно, могут прийти в обратном порядке, и на сервере осело бы не то
//      состояние, которое человек видит на экране.

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { api } from "../lib/api";
import { haptic } from "../lib/telegram";

interface FavoritesValue {
  ids: ReadonlySet<number>;
  isFavorite: (movieId: number) => boolean;
  toggle: (movieId: number) => void;
  /** Дождаться, пока все начатые записи дойдут до сервера (см. использование во вкладке). */
  flush: () => Promise<void>;
}

const FavoritesContext = createContext<FavoritesValue | null>(null);

export function FavoritesProvider({ enabled, children }: { enabled: boolean; children: ReactNode }) {
  const [ids, setIds] = useState<ReadonlySet<number>>(() => new Set());
  // Синхронное зеркало `ids`: состояние React обновляется к следующему рендеру, а
  // обработчику тапа ответ нужен ПРЯМО СЕЙЧАС (см. правило 1 в шапке).
  const idsRef = useRef<ReadonlySet<number>>(new Set());
  // Хвост очереди запросов по каждому фильму (правило 2).
  const queues = useRef(new Map<number, Promise<unknown>>());

  const apply = useCallback((next: ReadonlySet<number>) => {
    idsRef.current = next;
    setIds(next);
  }, []);

  /** Забрать список с сервера. Он же — способ починить любое расхождение после сбоя. */
  const reload = useCallback(async () => {
    try {
      apply(new Set((await api.favoriteIds()).ids));
    } catch {
      /* избранное не критично: не сложилось — звёзды просто останутся как есть */
    }
  }, [apply]);

  // Грузим один раз, когда приложение готово (до авторизации ручка отдала бы 401).
  useEffect(() => {
    if (!enabled) return;
    void reload();
  }, [enabled, reload]);

  const toggle = useCallback(
    (movieId: number) => {
      haptic.light();
      const added = !idsRef.current.has(movieId);
      const next = new Set(idsRef.current);
      if (added) next.add(movieId);
      else next.delete(movieId);
      apply(next);

      // Ставим запрос в хвост очереди этого фильма — порядок PUT/DELETE сохраняется.
      const tail = queues.current.get(movieId) ?? Promise.resolve();
      const chained = tail
        .catch(() => {}) // сбой предыдущего шага не должен обрывать цепочку
        .then(() => (added ? api.addFavorite(movieId) : api.removeFavorite(movieId)))
        .catch(() => {
          // Слепой откат тут опасен: человек мог успеть тапнуть ещё раз, и мы затёрли бы
          // его свежий выбор. Спрашиваем сервер — он знает, как на самом деле.
          void reload();
        });
      queues.current.set(movieId, chained);
    },
    [apply, reload],
  );

  // Вкладка «Таңдаулы» запрашивает список у сервера, и без этой синхронизации звезда,
  // поставленная за мгновение до перехода, не успевала бы долететь — фильм в списке не
  // появился бы, хотя звезда на нём горит.
  const flush = useCallback(async () => {
    await Promise.allSettled([...queues.current.values()]);
  }, []);

  const value = useMemo<FavoritesValue>(
    () => ({ ids, isFavorite: (movieId) => ids.has(movieId), toggle, flush }),
    [ids, toggle, flush],
  );

  return <FavoritesContext.Provider value={value}>{children}</FavoritesContext.Provider>;
}

/** Избранное текущего юзера. Вне провайдера — пустое и без действий (SSR/тесты не падают). */
export function useFavorites(): FavoritesValue {
  return (
    useContext(FavoritesContext) ?? {
      ids: new Set<number>(),
      isFavorite: () => false,
      toggle: () => {},
      flush: () => Promise.resolve(),
    }
  );
}
