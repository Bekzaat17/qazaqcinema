// Недельный бесплатный выбор — общее состояние на всё приложение.
//
// Контекст, а не пропсы, по той же причине, что у избранного: бейдж «Менің таңдауым»
// нужен постеру, который лежит в глубине четырёх разных деревьев (полки главной, сетка
// каталога, выдача поиска, вкладка избранного). Тащить туда id фильма пришлось бы через
// каждый промежуточный компонент, которому до недельного выбора нет дела.
//
// ⚠️ У подписчика значения тут ПУСТЫЕ (см. `App`): у него нет ни выбора, ни счётчика, и
// ни один элемент этой механики не имеет права появиться у него на экране.

import { createContext, useContext, useMemo, type ReactNode } from "react";

interface WeeklyPickValue {
  /** Фильм, выбранный на ТЕКУЩУЮ неделю. null — выбор свободен либо механика не про нас. */
  movieId: number | null;
  /** Когда закрывается окно (ISO). Один на всех. */
  endsAt: string | null;
}

const WeeklyPickContext = createContext<WeeklyPickValue>({ movieId: null, endsAt: null });

export function WeeklyPickProvider({
  movieId,
  endsAt,
  children,
}: WeeklyPickValue & { children: ReactNode }) {
  const value = useMemo(() => ({ movieId, endsAt }), [movieId, endsAt]);
  return <WeeklyPickContext.Provider value={value}>{children}</WeeklyPickContext.Provider>;
}

export function useWeeklyPick(): WeeklyPickValue {
  return useContext(WeeklyPickContext);
}
