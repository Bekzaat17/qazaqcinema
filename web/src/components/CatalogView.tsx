// Страница-каталог: липкая шапка (чипы-категории мультивыбор + сортировка) → сетка
// постеров 3-в-ряд → бесконечная подгрузка при скролле. Всю выборку/пагинацию делает
// бэкенд (`/api/movies`), фронт лишь рисует и гасит гонки страниц монотонным reqId.

import { ArrowDown, ArrowUp, Loader2, SearchX } from "lucide-react";
import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";

import { api, type CategoryCount, type Movie, type SortDir, type SortField } from "../lib/api";
import { categoryLabel } from "../lib/catalog";
import { haptic } from "../lib/telegram";
import Skeleton from "../ui/Skeleton";
import PosterCard from "./PosterCard";
import { LoadError } from "./States";

const PAGE_SIZE = 24;

const SORTS: { field: SortField; label: string }[] = [
  { field: "date", label: "Күні" },
  { field: "rating", label: "Рейтинг" },
  { field: "views", label: "Қаралым" },
];

export default function CatalogView({ onSelect }: { onSelect: (movie: Movie) => void }) {
  const [cats, setCats] = useState<CategoryCount[]>([]);
  const [selected, setSelected] = useState<string[]>([]); // пусто = все категории
  const [sort, setSort] = useState<SortField>("date");
  const [direction, setDirection] = useState<SortDir>("desc");

  const [items, setItems] = useState<Movie[]>([]);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const reqId = useRef(0);

  // Непустые категории для чипов — один раз.
  useEffect(() => {
    api
      .categories()
      .then(setCats)
      .catch(() => setCats([]));
  }, []);

  // Загрузка страницы. nextPage===1 — сброс (смена фильтра/сортировки); иначе — догрузка.
  const load = useCallback(
    async (nextPage: number) => {
      const id = ++reqId.current;
      if (nextPage === 1) setItems([]);
      setLoading(true);
      setError(false);
      try {
        const res = await api.browse(selected, sort, direction, nextPage, PAGE_SIZE);
        if (id !== reqId.current) return; // устаревший ответ — гасим гонку страниц
        setItems((prev) => (nextPage === 1 ? res.items : [...prev, ...res.items]));
        setHasMore(res.has_more);
        setPage(res.page);
      } catch {
        if (id === reqId.current) setError(true);
      } finally {
        if (id === reqId.current) setLoading(false);
      }
    },
    [selected, sort, direction],
  );

  // Смена фильтра/сортировки (новая identity load) → перезагрузка с первой страницы.
  useEffect(() => {
    void load(1);
  }, [load]);

  // Бесконечная прокрутка: догружаем при появлении сентинела. disconnect сразу после
  // срабатывания — чтобы одна и та же страница не подтянулась дважды.
  const sentinel = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const node = sentinel.current;
    if (!node || !hasMore || loading) return;
    const observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting) {
        observer.disconnect();
        void load(page + 1);
      }
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [hasMore, loading, page, load]);

  const toggleCategory = (slug: string) => {
    haptic.select();
    setSelected((prev) => (prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug]));
  };

  const chooseSort = (field: SortField) => {
    haptic.select();
    if (field === sort) setDirection((d) => (d === "desc" ? "asc" : "desc"));
    else {
      setSort(field);
      setDirection("desc");
    }
  };

  return (
    <div className="pb-4">
      <div className="sticky top-[57px] z-20 border-b border-white/5 bg-bg/90 backdrop-blur-xl">
        <div className="no-scrollbar flex gap-2 overflow-x-auto px-4 py-3">
          <Chip
            active={selected.length === 0}
            onClick={() => {
              haptic.select();
              setSelected([]);
            }}
          >
            Барлығы
          </Chip>
          {cats.map((c) => (
            <Chip key={c.slug} active={selected.includes(c.slug)} onClick={() => toggleCategory(c.slug)}>
              {categoryLabel(c.slug)}
            </Chip>
          ))}
        </div>
        <div className="flex items-center gap-1.5 px-4 pb-2.5">
          <span className="mr-1 text-xs text-faint">Сұрыптау</span>
          {SORTS.map(({ field, label }) => {
            const active = sort === field;
            return (
              <button
                key={field}
                onClick={() => chooseSort(field)}
                className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-[13px] font-medium transition-colors ${
                  active ? "bg-elevated text-text" : "text-muted active:text-text"
                }`}
              >
                {label}
                {active &&
                  (direction === "desc" ? <ArrowDown size={13} /> : <ArrowUp size={13} />)}
              </button>
            );
          })}
        </div>
      </div>

      {error && items.length === 0 ? (
        <LoadError onRetry={() => void load(1)} />
      ) : loading && items.length === 0 ? (
        <div className="grid grid-cols-3 gap-3 px-4 pt-4">
          {Array.from({ length: 9 }).map((_, i) => (
            <Skeleton key={i} className="aspect-[2/3] w-full" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <FilterEmpty />
      ) : (
        <>
          <div className="grid grid-cols-3 gap-3 px-4 pt-4">
            {items.map((movie) => (
              <PosterCard key={movie.id} movie={movie} onSelect={onSelect} inShelf={false} />
            ))}
          </div>
          <div ref={sentinel} className="h-8" />
          {loading && (
            <div className="flex justify-center py-4">
              <Loader2 size={22} className="animate-spin text-faint" />
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`shrink-0 rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors ${
        active ? "bg-brand text-white" : "border border-border bg-surface text-muted active:text-text"
      }`}
    >
      {children}
    </button>
  );
}

function FilterEmpty() {
  return (
    <div className="flex flex-col items-center px-8 py-16 text-center">
      <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-surface text-faint">
        <SearchX size={26} />
      </div>
      <p className="text-base font-semibold text-text">Осы сүзгі бойынша фильм жоқ</p>
      <p className="mt-1 text-sm text-muted">Басқа санатты таңдап көріңіз.</p>
    </div>
  );
}
