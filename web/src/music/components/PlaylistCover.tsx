// Обложка плейлиста: градиент из названия и нота. `icon` — для готовых подборок.

import { ListMusic, type LucideIcon } from "../../ui-kit/adapters/icons";

import { coverGradient } from "../format";

export default function PlaylistCover({ seed, Icon = ListMusic, className = "h-full w-full" }: { seed: string; Icon?: LucideIcon; className?: string }) {
  return (
    <div style={{ background: coverGradient(seed) }} className={`${className} flex items-center justify-center`}>
      <Icon size={34} className="text-white/85" />
    </div>
  );
}
