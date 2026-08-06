// Написать админам/техподдержке прямо из Mini App: шторка с полем ввода → POST /api/support.
// Сообщение уходит админам в личку Telegram, отвечают они там же (переписки в приложении нет —
// это не мессенджер, а витрина; ответ приходит от бота, где юзер и так сидит).

import { LifeBuoy, Send } from "lucide-react";
import { useEffect, useState } from "react";

import { ApiError, api } from "../lib/api";
import { haptic } from "../lib/telegram";
import Button from "../ui/Button";
import Sheet from "../ui/Sheet";

// Держим в одном месте с бэком (`SupportIn`: min_length=3, max_length=MAX_MESSAGE_LEN),
// чтобы юзер узнавал о лимите до отправки, а не по 422.
const MIN_LEN = 3;
const MAX_LEN = 2000;

interface SupportSheetProps {
  open: boolean;
  onClose: () => void;
  onSent: (message: string) => void;
  onError: (message: string) => void;
}

export default function SupportSheet({ open, onClose, onSent, onError }: SupportSheetProps) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);

  // Открыли заново — чистый лист (прошлое обращение уже ушло админам).
  useEffect(() => {
    if (open) setText("");
  }, [open]);

  const trimmed = text.trim();
  const ready = trimmed.length >= MIN_LEN && !sending;

  async function send() {
    if (!ready) return;
    setSending(true);
    try {
      await api.sendSupport(trimmed);
      haptic.success();
      onSent("Хабарлама жіберілді — жақын арада жауап береміз");
      onClose();
    } catch (e) {
      haptic.error();
      if (e instanceof ApiError && e.status === 429) {
        onError("Тым жиі жіберудесіз, сәл күте тұрыңыз");
      } else if (e instanceof ApiError && e.status === 502) {
        onError("Қолдау қазір қолжетімсіз, кейінірек көріңіз");
      } else {
        onError("Жіберілмеді, қайталап көріңіз");
      }
    } finally {
      setSending(false);
    }
  }

  return (
    <Sheet open={open} onClose={onClose} labelledBy="support-title">
      <div className="px-5 pb-2 pt-1">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-brand/15">
            <LifeBuoy size={22} className="text-brand" />
          </div>
          <div className="min-w-0">
            <h2 id="support-title" className="text-lg font-bold text-text">
              Қолдау қызметі
            </h2>
            <p className="text-sm text-faint">Сұрағыңызды жазыңыз — админдер жауап береді</p>
          </div>
        </div>

        <textarea
          value={text}
          onChange={(e) => setText(e.target.value.slice(0, MAX_LEN))}
          rows={5}
          autoComplete="off"
          placeholder="Мысалы: төлем жасадым, бірақ жазылым қосылмады"
          className="mt-4 w-full resize-none rounded-2xl border border-border bg-elevated p-4 text-[15px] text-text placeholder:text-faint focus:border-brand/60 focus:outline-none"
        />
        <div className="mt-1.5 flex justify-end text-xs text-faint tabular">
          {trimmed.length}/{MAX_LEN}
        </div>

        <div className="mt-3">
          <Button onClick={send} disabled={!ready} loading={sending}>
            <Send size={18} />
            Жіберу
          </Button>
        </div>
      </div>
    </Sheet>
  );
}
