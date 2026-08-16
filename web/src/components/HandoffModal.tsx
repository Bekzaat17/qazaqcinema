// Хэндофф-модалка (ключевой момент Фазы 9): видео не играется в Mini App — бот отправил
// его в чат. Показываем подтверждение + «Жабу» → WebApp.close(), юзер попадает к боту.

import { Clapperboard, Gift } from "lucide-react";

import Button from "../ui/Button";
import { close } from "../lib/telegram";

/** `gift` — видео ушло за счёт подарочного фильма: говорим об этом прямо, одним словом. */
export default function HandoffModal({ open, gift = false }: { open: boolean; gift?: boolean }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6">
      <div className="anim-fade absolute inset-0 bg-black/80 backdrop-blur-sm" />
      <div className="anim-pop relative w-full max-w-sm rounded-3xl border border-border bg-surface p-6 text-center shadow-2xl">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-brand/15">
          {gift ? <Gift size={30} className="text-brand" /> : <Clapperboard size={30} className="text-brand" />}
        </div>
        <h2 className="text-xl font-bold text-text">
          {gift ? "Сыйлық жіберілді 🎁" : "Видео ботқа жіберілді"}
        </h2>
        <p className="mt-2 text-[15px] leading-relaxed text-muted">
          Ботпен чаттан ашып қараңыз. Видео тек сол жерде — қауіпсіздік үшін жүктеп алуға болмайды.
        </p>
        <div className="mt-6">
          <Button onClick={close}>Чатқа өту</Button>
        </div>
      </div>
    </div>
  );
}
