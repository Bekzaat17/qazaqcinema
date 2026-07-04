// Пустые/ошибочные состояния.

import { Film, SearchX, WifiOff } from "lucide-react";
import type { ReactNode } from "react";

import Button from "../ui/Button";

function Wrap({ icon, title, hint, children }: { icon: ReactNode; title: string; hint?: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-8 py-20 text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-surface text-faint">{icon}</div>
      <p className="text-lg font-semibold text-text">{title}</p>
      {hint && <p className="mt-1.5 max-w-xs text-sm text-muted">{hint}</p>}
      {children && <div className="mt-5 w-full max-w-[220px]">{children}</div>}
    </div>
  );
}

export function CatalogEmpty() {
  return <Wrap icon={<Film size={28} />} title="Каталог толтырылып жатыр" hint="Жақында жаңа фильмдер мен аниме қосылады." />;
}

export function SearchEmpty({ query }: { query: string }) {
  return <Wrap icon={<SearchX size={28} />} title="Ештеңе табылмады" hint={`«${query}» бойынша нәтиже жоқ.`} />;
}

export function LoadError({ onRetry }: { onRetry: () => void }) {
  return (
    <Wrap icon={<WifiOff size={28} />} title="Жүктеу қатесі" hint="Байланысты тексеріп, қайталап көріңіз.">
      <Button variant="surface" onClick={onRetry}>
        Қайталау
      </Button>
    </Wrap>
  );
}
