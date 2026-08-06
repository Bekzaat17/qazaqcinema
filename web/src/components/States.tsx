// Пустые/ошибочные состояния.

import { Film, LayoutGrid, SearchX, Send, WifiOff } from "lucide-react";
import type { ReactNode } from "react";

import { BOT_USERNAME, BOT_URL } from "../lib/telegram";
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

/**
 * Экран для гостя, открывшего сайт в обычном браузере (чаще всего — из поисковой выдачи).
 * Раньше он получал только инструкцию «найдите такого-то бота» и уходил: описание без
 * кнопки — тупик. Теперь главное здесь — ссылка, ведущая прямо в бота (`?start=web`,
 * чтобы такие заходы были различимы), плюс запасной путь в SSR-каталог для тех, кому
 * сперва хочется посмотреть, что вообще есть.
 */
export function NotInTelegram() {
  return (
    <Wrap
      icon={<Send size={28} />}
      title="Telegram арқылы ашыңыз"
      hint={`Кинотеатр Telegram ішінде жұмыс істейді — төмендегі батырма сізді ${BOT_USERNAME} ботына апарады.`}
    >
      <div className="flex flex-col gap-2.5">
        <a
          href={`${BOT_URL}?start=web`}
          rel="noopener"
          className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-brand px-5 py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-brand/25 transition-transform duration-150 active:scale-[0.98]"
        >
          <Send size={18} />
          Telegram-да ашу
        </a>
        <a
          href="/catalog"
          className="inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-border bg-elevated px-5 py-3 text-sm font-medium text-muted active:bg-surface-2"
        >
          <LayoutGrid size={16} />
          Каталогты қарау
        </a>
      </div>
    </Wrap>
  );
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
