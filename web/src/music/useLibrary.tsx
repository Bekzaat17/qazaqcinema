// «Менің музыкам» — множество сохранённых треков на весь раздел.
//
// Тот же приём, что у избранного кинотеатра (`hooks/useFavorites`): сердце в строке трека
// живёт в глубине нескольких экранов, а тумблер оптимистичный и с очередью запросов на
// каждый трек — иначе быстрые тапы приходят на сервер в обратном порядке.

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { haptic } from "../lib/telegram";
import { musicApi } from "./api";

interface LibraryValue {
  has: (trackId: number) => boolean;
  toggle: (trackId: number) => boolean;
  /** Растёт на каждое изменение — экран «Менің музыкам» по нему перечитывает список. */
  version: number;
}

const LibraryContext = createContext<LibraryValue | null>(null);

export function LibraryProvider({ enabled, children }: { enabled: boolean; children: ReactNode }) {
  const [ids, setIds] = useState<ReadonlySet<number>>(() => new Set());
  const [version, setVersion] = useState(0);
  const idsRef = useRef<ReadonlySet<number>>(new Set());
  const queues = useRef(new Map<number, Promise<unknown>>());

  const apply = useCallback((next: ReadonlySet<number>) => {
    idsRef.current = next;
    setIds(next);
  }, []);

  useEffect(() => {
    if (!enabled) return;
    musicApi.libraryIds().then(
      (res) => apply(new Set(res.ids)),
      () => {},
    );
  }, [enabled, apply]);

  const toggle = useCallback(
    (trackId: number) => {
      haptic.light();
      const added = !idsRef.current.has(trackId);
      const next = new Set(idsRef.current);
      if (added) next.add(trackId);
      else next.delete(trackId);
      apply(next);
      const tail = queues.current.get(trackId) ?? Promise.resolve();
      const chained = tail
        .catch(() => {})
        .then(() => (added ? musicApi.save(trackId) : musicApi.unsave(trackId)))
        .then(() => setVersion((v) => v + 1))
        .catch(() => {
          // Сервер не принял — откатываем ровно этот трек.
          const rollback = new Set(idsRef.current);
          if (added) rollback.delete(trackId);
          else rollback.add(trackId);
          apply(rollback);
        });
      queues.current.set(trackId, chained);
      return added;
    },
    [apply],
  );

  const value = useMemo<LibraryValue>(
    () => ({ has: (trackId) => ids.has(trackId), toggle, version }),
    [ids, toggle, version],
  );
  return <LibraryContext.Provider value={value}>{children}</LibraryContext.Provider>;
}

export function useLibrary(): LibraryValue {
  const value = useContext(LibraryContext);
  if (!value) throw new Error("useLibrary вне LibraryProvider");
  return value;
}
