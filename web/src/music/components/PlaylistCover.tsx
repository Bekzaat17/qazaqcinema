// Обложка плейлиста: мозаика 2×2 из обложек треков либо градиент с нотой.

import { ListMusic } from "../../ui-kit/adapters/icons";

import { coverGradient } from "../format";

export default function PlaylistCover({ covers, seed, className = "h-full w-full" }: { covers: string[]; seed: string; className?: string }) {
  if (covers.length >= 4) {
    return (
      <div className={`${className} grid grid-cols-2 grid-rows-2 overflow-hidden`}>
        {covers.slice(0, 4).map((src) => (
          <img key={src} src={src} alt="" loading="lazy" className="h-full w-full object-cover" />
        ))}
      </div>
    );
  }
  if (covers.length > 0) {
    return <img src={covers[0]} alt="" loading="lazy" className={`${className} object-cover`} />;
  }
  return (
    <div style={{ background: coverGradient(seed) }} className={`${className} flex items-center justify-center`}>
      <ListMusic size={34} className="text-white/85" />
    </div>
  );
}
