// Липкая шапка: компактный логотип слева, профиль/статус справа.

import { CircleUserRound } from "lucide-react";

import type { UserStatus } from "../lib/api";
import { haptic } from "../lib/telegram";

const STATUS_DOT: Partial<Record<UserStatus, string>> = {
  active: "bg-success",
  pending_review: "bg-star",
};

export default function TopBar({ status, onProfile }: { status: UserStatus; onProfile: () => void }) {
  const dot = STATUS_DOT[status];
  return (
    <header className="sticky top-0 z-30 flex items-center justify-between border-b border-white/5 bg-bg/80 px-4 py-3 backdrop-blur-xl">
      <div className="flex items-center gap-2">
        <img src="/logo-icon.png" alt="" className="h-8 w-8 shrink-0" />
        <span className="font-display text-lg font-bold leading-none tracking-tight">
          <span className="text-text">Qazaq</span>
          <span className="text-brand">Cinema</span>
        </span>
      </div>
      <button
        onClick={() => {
          haptic.light();
          onProfile();
        }}
        aria-label="Профиль"
        className="relative rounded-full p-1.5 text-muted transition-colors active:bg-elevated active:text-text"
      >
        <CircleUserRound size={26} strokeWidth={1.75} />
        {dot && (
          <span className={`absolute right-1 top-1 h-2.5 w-2.5 rounded-full ring-2 ring-bg ${dot}`} />
        )}
      </button>
    </header>
  );
}
