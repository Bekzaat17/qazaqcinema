// Поиск отдельной строкой во всю ширину (PLAN: не рядом с лого).

import { Search, X } from "lucide-react";

interface SearchBarProps {
  value: string;
  onChange: (v: string) => void;
}

export default function SearchBar({ value, onChange }: SearchBarProps) {
  return (
    <div className="px-4 pt-3">
      <div className="flex items-center gap-2.5 rounded-2xl border border-border bg-surface px-3.5 py-2.5 focus-within:border-brand/50">
        <Search size={18} className="shrink-0 text-faint" />
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          type="text"
          inputMode="search"
          placeholder="Фильм іздеу…"
          className="w-full bg-transparent text-[15px] text-text placeholder:text-faint focus:outline-none"
        />
        {value && (
          <button onClick={() => onChange("")} aria-label="Тазарту" className="shrink-0 text-faint active:text-text">
            <X size={18} />
          </button>
        )}
      </div>
    </div>
  );
}
