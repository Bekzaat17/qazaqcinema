// Обложка трека — цветная плитка с инициалами. Картинок нет намеренно: сервер музыку и
// её обложки не хранит (как и видео), а цвет из названия у трека всегда один и тот же.

import { coverGradient, initials } from "../format";

interface CoverProps {
  title: string;
  performer: string;
  className?: string;
  rounded?: string;
  textSize?: string;
}

export default function Cover({ title, performer, className = "h-12 w-12", rounded = "rounded-xl", textSize = "text-sm" }: CoverProps) {
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
