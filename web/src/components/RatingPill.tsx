import { Star } from "lucide-react";

/** Компактный бейдж рейтинга со звездой. */
export default function RatingPill({ rating, className = "" }: { rating: number; className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full bg-black/60 px-2 py-0.5 text-xs font-semibold text-white backdrop-blur-sm ${className}`}
    >
      <Star size={12} className="fill-star text-star" />
      <span className="tabular">{rating.toFixed(1)}</span>
    </span>
  );
}
