// Профиль (👤): аватар + имя + карточка статуса подписки + тумблер рассылок.

import { BadgeCheck, Bell, CalendarClock, Clock, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import type { Auth } from "../lib/api";
import { api } from "../lib/api";
import { daysLeft, formatDate, initials } from "../lib/format";
import { getTelegramUser, haptic } from "../lib/telegram";
import Button from "../ui/Button";
import Sheet from "../ui/Sheet";

interface ProfileSheetProps {
  open: boolean;
  auth: Auth | null;
  onClose: () => void;
  onSubscribe: () => void;
  onNotificationsChange: (enabled: boolean) => void;
}

export default function ProfileSheet({
  open,
  auth,
  onClose,
  onSubscribe,
  onNotificationsChange,
}: ProfileSheetProps) {
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

        {auth && (
          <div className="mt-3">
            <NotificationsToggle
              enabled={auth.notifications_enabled}
              onChange={onNotificationsChange}
            />
          </div>
        )}
      </div>
    </Sheet>
  );
}

function NotificationsToggle({
  enabled,
  onChange,
}: {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
}) {
  // Локальное состояние для оптимистичного переключения; синхронизируем, если auth обновился.
  const [on, setOn] = useState(enabled);
  const [saving, setSaving] = useState(false);
  useEffect(() => setOn(enabled), [enabled]);

  async function toggle() {
    if (saving) return;
    const next = !on;
    haptic.select();
    setOn(next); // оптимистично
    setSaving(true);
    try {
      await api.setNotifications(next);
      onChange(next); // поднимаем в App, чтобы переоткрытие показало актуальное
    } catch {
      setOn(!next); // откат
      haptic.error();
    } finally {
      setSaving(false);
    }
  }

  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={toggle}
      className="flex w-full items-center gap-3 rounded-2xl border border-border bg-elevated p-4 text-left"
    >
      <Bell size={20} className="shrink-0 text-brand" />
      <span className="min-w-0 flex-1 text-sm font-medium text-text">
        Жаңа фильмдер туралы хабарлау
      </span>
      <span
        className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
          on ? "bg-brand" : "bg-border"
        }`}
      >
        <span
          className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${
            on ? "translate-x-[22px]" : "translate-x-0.5"
          }`}
        />
      </span>
    </button>
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
