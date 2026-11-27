// Обложка трека: картинка из тегов файла либо цветная заглушка с инициалами.
// Цвет заглушки выводится из названия — у одного трека он всегда один и тот же.

import { useState } from "react";

import { coverGradient, initials } from "../format";

interface CoverProps {
  title: string;
  performer: string;
  url: string | null;
  className?: string;
  rounded?: string;
  textSize?: string;
}

export default function Cover({ title, performer, url, className = "h-12 w-12", rounded = "rounded-xl", textSize = "text-sm" }: CoverProps) {
  const [broken, setBroken] = useState(false);
  if (url && !broken) {
    return (
      <img
        src={url}
        alt=""
        loading="lazy"
        onError={() => setBroken(true)}
        className={`${className} ${rounded} shrink-0 bg-surface-2 object-cover`}
      />
    );
  }
  return (
    <div
      aria-hidden="true"
      style={{ background: coverGradient(`${performer}${title}`) }}
      className={`${className} ${rounded} flex shrink-0 items-center justify-center font-bold text-white/90 ${textSize}`}
    >
      {initials(performer || title)}
    </div>
  );
}
