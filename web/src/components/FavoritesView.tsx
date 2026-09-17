// Вкладка «Таңдаулы»: недельный выбор + личный список отмеченных звездой фильмов.
//
// Список грузится при каждом открытии вкладки (компонент монтируется заново), но
// отображаемое дополнительно фильтруется по актуальным id из контекста. Благодаря этому
// снятая звезда убирает карточку СРАЗУ, без похода на сервер и без мигания списка.
//
// Гейта подписки тут нет: избранное — часть свободного каталога, по которому человек
// ходит ещё до оплаты.
//
// Недельный фильм стоит ПЕРВЫМ отдельной секцией: это единственное кино, которое человеку
// прямо сейчас ничего не стоит, и второе место после профиля, куда он идёт его искать.
// У подписчика контекст `useWeeklyPick` пустой — значит секции у него нет вообще.

import { useEffect, useState } from "react";

import { useFavorites } from "../hooks/useFavorites";
import { useWeeklyPick } from "../hooks/useWeeklyPick";
import { api, type Movie } from "../lib/api";
import { weekLeftLabel } from "../lib/week";
import Skeleton from "../ui/Skeleton";
import { FavoritesEmpty, LoadError } from "./States";
import PosterCard from "./PosterCard";
import WeeklyPickCard from "./WeeklyPickCard";

const GRID = "grid grid-cols-3 gap-3 px-4 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6";

export default function FavoritesView({ onSelect }: { onSelect: (movie: Movie) => void }) {
  const { ids, flush } = useFavorites();
  const { movieId: weeklyId, endsAt } = useWeeklyPick();
  const [movies, setMovies] = useState<Movie[] | null>(null);
  const [weekly, setWeekly] = useState<Movie | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0); // ++ по «Қайталау» → перезапуск загрузки

  useEffect(() => {
    let alive = true;
    setFailed(false);
    // Сначала ждём, пока долетят звёзды, поставленные секунду назад на главной или в
    // каталоге. Без этого список пришёл бы без них — самый заметный вид «глюка»:
    // звезда горит, а во вкладке фильма нет.
    flush()
      .then(() =>
        Promise.all([
          api.favorites(),
          // Недельный фильм тянем отдельным запросом: в избранном его может и не быть, а
          // сбой этого запроса не имеет права уронить сам список — секция просто не
          // появится, звёзды человек увидит.
          weeklyId === null ? null : api.getMovie(weeklyId).catch(() => null),
        ]),
      )
      .then(([favorites, pick]) => {
        if (!alive) return;
        setMovies(favorites);
        setWeekly(pick);
      })
      .catch(() => {
        if (alive) setFailed(true);
      });
    return () => {
      alive = false;
    };
    // Перезапрос на каждое изменение `ids` означал бы поход на сервер после каждого тапа
    // по звезде; снятие обрабатывает фильтр ниже, а `attempt` — кнопка «Қайталау».
  }, [attempt, flush, weeklyId]);

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
      <div className={`${GRID} pt-4`}>
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="aspect-[2/3] w-full" />
        ))}
      </div>
    );
  }

  // Недельный фильм из сетки убираем, даже если он в избранном: два одинаковых постера
  // на одном коротком экране читаются как сбой, а звезда у него осталась на карточке
  // выше — снять её по-прежнему можно там же.
  const visible = movies.filter((movie) => ids.has(movie.id) && movie.id !== weekly?.id);
  if (weekly === null && visible.length === 0) return <FavoritesEmpty />;

  const left = weekLeftLabel(endsAt);

  return (
    <>
      {weekly && (
        // Заголовка над карточкой нет: она сама себя называет бейджем, а лишняя строка
        // только отодвигала бы витрину вниз.
        <div className="px-4 pt-4">
          <WeeklyPickCard movie={weekly} left={left} onSelect={onSelect} />
        </div>
      )}

      <section className={weekly ? "mt-6" : "pt-4"}>
        {/* Заголовок нужен только когда выше есть другая секция: без него две сетки
            слиплись бы в одну, и недельный фильм выглядел бы просто первым избранным. */}
        {weekly && (
          <h2 className="mb-3 px-4 text-[17px] font-bold tracking-tight text-text">Таңдаулы</h2>
        )}
        {visible.length === 0 ? (
          // Полноэкранная заглушка тут не к месту — над ней уже стоит секция с фильмом.
          <p className="px-4 text-sm text-muted">
            Ұнаған фильмнің жұлдызшасын басыңыз — ол осында жиналады.
          </p>
        ) : (
          <div className={GRID}>
            {visible.map((movie) => (
              <PosterCard key={movie.id} movie={movie} onSelect={onSelect} inShelf={false} />
            ))}
          </div>
        )}
      </section>
    </>
  );
}
