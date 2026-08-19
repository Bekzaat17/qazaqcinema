// Hero главного экрана = ФИЛЬМ ДНЯ (решение 2026-08-19).
//
// Раньше здесь висела просто курируемая карточка: человек жал «Көру» и упирался в
// пэйволл — лучшее место экрана ничего не обещало. Теперь оно обещает конкретное: вот
// это кино сегодня можно посмотреть бесплатно. Отсюда и состав блока: бейдж «Бүгін
// тегін», обратный отсчёт до смены и одна пульсирующая кнопка «Тегін көру».
//
// ВЁРСТКА ОДНА, и она рассчитана на единственную картинку фильма — постер 2:3.
// Широкий баннер больше не собирается (просить у админа вторую картинку к каждому из
// сотен фильмов — работа, которая ничего не добавляет), поэтому широкую поверхность мы
// делаем из постера: фоном идёт ТОТ ЖЕ файл, увеличенный и размытый, а поверх лежит его
// чёткая копия. Постер 2:3 нельзя ни растянуть, ни обрезать до 3:2 — кадр скомпонован
// вертикально, центр-кроп режет лицо и название. Зато размытая копия даёт фон в цветах
// самого фильма: блок каждый день выглядит нарисованным под сегодняшнее кино.
//
// Клик по площади открывает карточку фильма, клик по кнопке сразу шлёт видео — поэтому
// подложка это отдельная невидимая кнопка, а не обёртка (кнопка в кнопке невалидна).

import { Gift, Play, Timer } from "lucide-react";

import { useCountdown } from "../hooks/useCountdown";
import type { Movie } from "../lib/api";
import { haptic } from "../lib/telegram";
import RatingPill from "./RatingPill";

interface HeroProps {
  movie: Movie;
  /** До какого момента фильм бесплатен (ISO с бэка). null → обычная витрина без бейджа. */
  freeUntil: string | null;
  busy: boolean;
  onSelect: (movie: Movie) => void;
  onWatch: (movie: Movie) => void;
}

export default function Hero({ movie, freeUntil, busy, onSelect, onWatch }: HeroProps) {
  const left = useCountdown(freeUntil);
  const free = freeUntil !== null;

  return (
    <section className="relative isolate aspect-[4/3] max-h-[420px] w-full overflow-hidden">
      {/* Подложка = тот же постер: цвета фильма, но никакой читаемой детали. `scale`
          обязателен — blur размывает и КРАЯ, без наплыва по периметру шли бы полосы. */}
      <img
        src={movie.poster_url}
        alt=""
        aria-hidden
        className="anim-breathe absolute inset-0 h-full w-full scale-[1.12] object-cover blur-2xl saturate-150"
      />
      {/* Контраст текста не зависит от того, насколько светлым оказался постер */}
      <div className="absolute inset-0 bg-bg/55" />
      {/* Низ растворяем в фоне страницы — блок переходит в полки без шва */}
      <div className="absolute inset-0 bg-gradient-to-t from-bg via-bg/35 to-transparent" />
      {/* ...и ВЕРХ тем же фоном: без этого размытая подложка обрывалась ровной линией
          под поиском — единственный жёсткий край на всём экране. */}
      <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-bg via-bg/55 to-transparent" />

      <button
        type="button"
        onClick={() => {
          haptic.light();
          onSelect(movie);
        }}
        aria-label={`${movie.title_kk} — толығырақ`}
        className="absolute inset-0 z-10"
      />

      <div className="pointer-events-none relative z-20 flex h-full items-center gap-4 px-4">
        {/* Чёткий постер — «физическая» афиша на световом пятне: кольцо + глубокая тень */}
        <img
          src={movie.poster_url}
          alt={movie.title_kk}
          className="aspect-[2/3] w-[34%] max-w-[136px] shrink-0 rounded-2xl object-cover shadow-[0_16px_44px_rgb(0_0_0/0.65)] ring-1 ring-white/15"
        />
        <div className="flex min-w-0 flex-col items-start gap-2">
          {free && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-brand/20 px-2.5 py-1 text-[11px] font-extrabold uppercase tracking-[0.08em] text-brand-050 ring-1 ring-inset ring-brand/40 backdrop-blur-sm">
              <Gift size={12} />
              Бүгін тегін
            </span>
          )}
          <h1 className="line-clamp-2 text-[20px] font-extrabold leading-[1.15] tracking-tight text-white drop-shadow-lg">
            {movie.title_kk}
          </h1>
          {movie.title_original && (
            <p className="-mt-1 w-full truncate text-xs text-white/55">{movie.title_original}</p>
          )}
          <div className="flex items-center gap-2.5 text-[13px] text-white/80">
            {movie.rating != null && <RatingPill rating={movie.rating} />}
            {movie.year != null && <span className="tabular">{movie.year}</span>}
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              haptic.medium();
              onWatch(movie);
            }}
            className={`pointer-events-auto inline-flex items-center justify-center gap-2 rounded-2xl bg-brand px-5 py-3 text-sm font-bold text-white shadow-lg shadow-brand/30 transition-transform duration-150 active:scale-[0.98] disabled:opacity-60 ${
              free ? "anim-pulse-ring" : ""
            }`}
          >
            <Play size={16} className="fill-white" />
            {free ? "Тегін көру" : "Көру"}
          </button>
          {left && (
            <span className="inline-flex items-center gap-1.5 text-[12px] font-medium text-white/70">
              <Timer size={13} />
              <span className="tabular">{left}</span> қалды
            </span>
          )}
        </div>
      </div>
    </section>
  );
}
