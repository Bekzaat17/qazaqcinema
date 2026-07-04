// Горизонтальная полка (scroll-snap, нативная инерция, без JS-каруселей).

import type { Movie } from "../lib/api";
import type { Shelf as ShelfData } from "../lib/catalog";
import PosterCard from "./PosterCard";

export default function Shelf({ shelf, onSelect }: { shelf: ShelfData; onSelect: (m: Movie) => void }) {
  return (
    <section className="mt-6">
      <h2 className="mb-3 px-4 text-[17px] font-bold tracking-tight text-text">{shelf.title}</h2>
      <div className="no-scrollbar flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-1">
        {shelf.movies.map((movie) => (
          <PosterCard key={movie.id} movie={movie} onSelect={onSelect} />
        ))}
      </div>
    </section>
  );
}
