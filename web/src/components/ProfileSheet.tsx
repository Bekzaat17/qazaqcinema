// Профиль (👤): аватар + имя + карточка статуса подписки.

import { BadgeCheck, CalendarClock, Clock, Sparkles } from "lucide-react";

import type { Auth } from "../lib/api";
import { daysLeft, formatDate, initials } from "../lib/format";
import { getTelegramUser } from "../lib/telegram";
import Button from "../ui/Button";
import Sheet from "../ui/Sheet";

interface ProfileSheetProps {
  open: boolean;
  auth: Auth | null;
  onClose: () => void;
  onSubscribe: () => void;
}

export default function ProfileSheet({ open, auth, onClose, onSubscribe }: ProfileSheetProps) {
  const tgUser = getTelegramUser();
  const name = tgUser ? [tgUser.first_name, tgUser.last_name].filter(Boolean).join(" ") : "Қонақ";
  const handle = tgUser?.username ? `@${tgUser.username}` : "";

  return (
    <Sheet open={open} onClose={onClose} labelledBy="profile-title">
      <div className="px-5 pb-2 pt-1">
        <div className="flex items-center gap-3.5">
          {tgUser?.photo_url ? (
            <img src={tgUser.photo_url} alt={name} className="h-14 w-14 rounded-full object-cover" />
          ) : (
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-brand/15 text-lg font-bold text-brand">
              {initials(name)}
            </div>
          )}
          <div className="min-w-0">
            <h2 id="profile-title" className="truncate text-lg font-bold text-text">
              {name}
            </h2>
            {handle && <p className="truncate text-sm text-faint">{handle}</p>}
          </div>
        </div>

        <div className="mt-5">
          <StatusCard auth={auth} onSubscribe={onSubscribe} />
        </div>
      </div>
    </Sheet>
  );
}

function StatusCard({ auth, onSubscribe }: { auth: Auth | null; onSubscribe: () => void }) {
  if (auth?.status === "active") {
    const left = daysLeft(auth.expires_at);
    return (
      <div className="rounded-2xl border border-success/20 bg-success/5 p-4">
        <div className="flex items-center gap-2 text-success">
          <BadgeCheck size={20} />
          <span className="font-semibold">Жазылым белсенді</span>
        </div>
        <p className="mt-3 text-3xl font-extrabold text-text tabular">
          {left} <span className="text-lg font-semibold text-muted">күн қалды</span>
        </p>
        <div className="mt-2 flex items-center gap-1.5 text-sm text-faint">
          <CalendarClock size={15} />
          <span>{formatDate(auth.expires_at)} дейін</span>
        </div>
      </div>
    );
  }

  if (auth?.status === "pending_review") {
    return (
      <div className="rounded-2xl border border-star/25 bg-star/10 p-4">
        <div className="flex items-center gap-2 text-star">
          <Clock size={20} />
          <span className="font-semibold">Чек тексерілуде</span>
        </div>
        <p className="mt-2 text-sm text-muted">Төлеміңізді тексеріп жатырмыз — жақын арада хабарласамыз.</p>
      </div>
    );
  }

  // new / expired — предлагаем оформить.
  return (
    <div className="rounded-2xl border border-border bg-elevated p-4">
      <div className="flex items-center gap-2 text-muted">
        <Sparkles size={20} className="text-brand" />
        <span className="font-semibold text-text">Жазылым жоқ</span>
      </div>
      <p className="mt-2 mb-4 text-sm text-muted">
        Барлық фильмдер мен аниме — қазақша дубляжбен. Жазылып, көруді бастаңыз.
      </p>
      <Button onClick={onSubscribe}>Жазылу</Button>
    </div>
  );
}
