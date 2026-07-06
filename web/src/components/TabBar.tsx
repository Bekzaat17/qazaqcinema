// Нижняя навигация: ФИКСИРОВАННЫЙ таб-бар (Басты | Каталог), всегда виден при скролле.
// Оверлеи (карточка/пэйволл/профиль) перекрывают его своим бэкдропом (z выше). Профиль —
// отдельной иконкой в топбаре (это аккаунт, а не раздел-витрина).

import { Home, LayoutGrid, type LucideIcon } from "lucide-react";

import { haptic } from "../lib/telegram";

export type Tab = "home" | "catalog";

const TABS: { id: Tab; label: string; Icon: LucideIcon }[] = [
  { id: "home", label: "Басты", Icon: Home },
  { id: "catalog", label: "Каталог", Icon: LayoutGrid },
];

export default function TabBar({ tab, onChange }: { tab: Tab; onChange: (t: Tab) => void }) {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 flex border-t border-white/5 bg-bg/90 pb-[var(--safe-bottom)] backdrop-blur-xl">
      {TABS.map(({ id, label, Icon }) => {
        const active = tab === id;
        return (
          <button
            key={id}
            onClick={() => {
              haptic.light();
              onChange(id);
            }}
            aria-label={label}
            aria-current={active ? "page" : undefined}
            className={`flex flex-1 flex-col items-center gap-1 py-2.5 transition-colors ${
              active ? "text-brand" : "text-faint active:text-muted"
            }`}
          >
            <Icon size={23} strokeWidth={active ? 2.4 : 2} />
            <span className="text-[11px] font-medium leading-none">{label}</span>
          </button>
        );
      })}
    </nav>
  );
}
