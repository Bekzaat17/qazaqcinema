// Плашка после отправки: треки в чате, Telegram сыграет их по порядку. Кнопка уводит в чат.
//
// Из чата (кнопка меню, клавиатура бота) достаточно закрыть Mini App — под ним тот самый
// чат. У прямой ссылки под нами канал или браузер, поэтому открываем чат бота ссылкой
// (тот же выбор, что у `HandoffModal` кинотеатра).

import { useEffect } from "react";

import { MessageCircle, X } from "../../ui-kit/adapters/icons";

import { closeApp, getLaunch, haptic, openBotChat } from "../../lib/telegram";

const VISIBLE_MS = 7000;

export default function SentBar({ count, onClose }: { count: number; onClose: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onClose, VISIBLE_MS);
    return () => clearTimeout(timer);
  }, [count, onClose]);

  return (
    <div className="fixed inset-x-0 bottom-[calc(64px+var(--safe-bottom))] z-[45] mx-auto max-w-[1024px] px-3">
      <div className="anim-pop flex items-center gap-3 rounded-2xl border border-music/30 bg-elevated/95 p-3 shadow-[0_10px_30px_rgba(0,0,0,0.5)] backdrop-blur-xl">
        <span className="qm-gradient flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-lg">🎧</span>
        <div className="min-w-0 flex-1">
          <p className="text-[14px] font-bold text-text">
            {count > 1 ? `${count} ән чатқа жіберілді` : "Ән чатқа жіберілді"}
          </p>
          <p className="text-[12px] leading-snug text-muted">
            {count > 1 ? "Telegram оларды ретімен ойнатады — экран сөнсе де." : "Telegram-да ойнатыңыз — экран сөнсе де тыңдалады."}
          </p>
        </div>
        <button
          onClick={() => {
            haptic.light();
            if (getLaunch() === "chat") closeApp();
            else openBotChat();
          }}
          className="flex shrink-0 items-center gap-1.5 rounded-full bg-white px-3 py-2 text-[13px] font-bold text-black active:scale-95"
        >
          <MessageCircle size={15} /> Чатқа
        </button>
        <button onClick={onClose} aria-label="Жабу" className="-ml-1 p-1 text-faint">
          <X size={16} />
        </button>
      </div>
    </div>
  );
}
