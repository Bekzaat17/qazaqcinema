// Липкая шапка: компактный логотип слева, профиль/статус справа.

import { CircleUserRound, Headphones } from "../ui-kit/adapters/icons";

import { Brand } from "../ui-kit";
import type { UserStatus } from "../lib/api";
import { haptic } from "../lib/telegram";
import { navigateApp } from "../music/launch";

const STATUS_DOT: Partial<Record<UserStatus, string>> = {
  active: "bg-success",
  pending_review: "bg-star",
};

export default function TopBar({
  status,
  onProfile,
}: {
  status: UserStatus;
  onProfile: () => void;
}) {
  const dot = STATUS_DOT[status];
  return (
    <header className="sticky top-0 z-30 flex items-center justify-between border-b border-white/5 bg-bg/80 px-4 py-3 backdrop-blur-xl">
      <Brand product="cinema" compact />
      <div className="flex items-center gap-2">
        <a
          href="/music"
          onClick={(event) => {
            event.preventDefault();
            haptic.light();
            navigateApp("music");
          }}
          aria-label="QazaqMusic — музыка тыңдау және плейлистер"
          className="ui-switch-entry ui-switch-entry--music"
        >
          <Headphones size={17} />
          <span>Музыка</span>
        </a>
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
            <span
              className={`absolute right-1 top-1 h-2.5 w-2.5 rounded-full ring-2 ring-bg ${dot}`}
            />
          )}
        </button>
      </div>
    </header>
  );
}
