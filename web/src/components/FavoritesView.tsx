// Вкладка «Таңдаулы»: личный список отмеченных звездой фильмов.
//
// Список грузится при каждом открытии вкладки (компонент монтируется заново), но
// отображаемое дополнительно фильтруется по актуальным id из контекста. Благодаря этому
// снятая звезда убирает карточку СРАЗУ, без похода на сервер и без мигания списка.
//
// Гейта подписки тут нет: избранное — часть свободного каталога, по которому человек
// ходит ещё до оплаты.

import { useEffect, useState } from "react";

import { useFavorites } from "../hooks/useFavorites";
import { api, type Movie } from "../lib/api";
import Skeleton from "../ui/Skeleton";
import { FavoritesEmpty, LoadError } from "./States";
import PosterCard from "./PosterCard";

export default function FavoritesView({ onSelect }: { onSelect: (movie: Movie) => void }) {
  const { ids, flush } = useFavorites();
  const [movies, setMovies] = useState<Movie[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0); // ++ по «Қайталау» → перезапуск загрузки

  useEffect(() => {
    let alive = true;
    setFailed(false);
    // Сначала ждём, пока долетят звёзды, поставленные секунду назад на главной или в
    // каталоге. Без этого список пришёл бы без них — самый заметный вид «глюка»:
    // звезда горит, а во вкладке фильма нет.
    flush()
      .then(() => api.favorites())
      .then((res) => {
        if (alive) setMovies(res);
      })
      .catch(() => {
        if (alive) setFailed(true);
      });
    return () => {
      alive = false;
    };
    // Перезапрос на каждое изменение `ids` означал бы поход на сервер после каждого тапа
    // по звезде; снятие обрабатывает фильтр ниже, а `attempt` — кнопка «Қайталау».
  }, [attempt, flush]);

  if (failed) {
    return (
      <LoadError
        onRetry={() => {
          setMovies(null);
          setAttempt((n) => n + 1);
        }}
      />
    );
  }
  if (movies === null) {
    return (
      <div className="grid grid-cols-3 gap-3 px-4 pt-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="aspect-[2/3] w-full" />
        ))}
      </div>
    );
  }

  const visible = movies.filter((movie) => ids.has(movie.id));
  if (visible.length === 0) return <FavoritesEmpty />;

  return (
    <div className="grid grid-cols-3 gap-3 px-4 pt-4">
      {visible.map((movie) => (
        <PosterCard key={movie.id} movie={movie} onSelect={onSelect} inShelf={false} />
      ))}
    </div>
  );
}
