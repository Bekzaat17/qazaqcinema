// Звезда «в избранное». Два размера одного поведения: крупная в карточке фильма и
// компактная поверх постера в лентах.
//
// На постере это ОТДЕЛЬНАЯ кнопка поверх кнопки-карточки, поэтому клик обязан гаситься
// (`stopPropagation`) — иначе тап по звезде заодно открывал бы карточку фильма.

import { Star } from "lucide-react";

import { useFavorites } from "../hooks/useFavorites";

interface FavoriteButtonProps {
  movieId: number;
  /** `overlay` — поверх постера в ленте; `inline` — в ряд с «Көру» в карточке. */
  variant?: "overlay" | "inline";
}

export default function FavoriteButton({ movieId, variant = "overlay" }: FavoriteButtonProps) {
  const { isFavorite, toggle } = useFavorites();
  const active = isFavorite(movieId);
  const label = active ? "Таңдаулыдан алып тастау" : "Таңдаулыға қосу";

  const base =
    "flex items-center justify-center transition-colors active:scale-95 " +
    (active ? "text-brand" : "text-white/70");
  const shape =
    variant === "overlay"
      ? // Полупрозрачная подложка: постеры бывают светлыми, и белая звезда на них терялась.
        "absolute left-1.5 top-1.5 h-8 w-8 rounded-full bg-black/45 backdrop-blur-sm"
      : "h-12 w-12 shrink-0 rounded-2xl border border-border bg-elevated";

  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={active}
      title={label}
      onClick={(e) => {
        e.stopPropagation(); // на постере звезда лежит внутри кнопки-карточки
        toggle(movieId);
      }}
      className={`${base} ${shape}`}
    >
      <Star
        size={variant === "overlay" ? 16 : 21}
        strokeWidth={2.2}
        className={active ? "fill-brand" : ""}
      />
    </button>
  );
}
