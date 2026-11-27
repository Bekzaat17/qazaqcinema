// «Қосу»: как пополнить общий каталог и что сейчас просят.
//
// Каталог растёт силами слушателей: аудио из любого Telegram-чата или канала пересылается
// боту и сразу становится доступно всем. Экран объясняет это в три шага и показывает
// запросы — что людям нужно прямо сейчас.

import { Forward, MessageCircle, Music2, Send, Sparkles } from "../ui-kit/adapters/icons";

import { openBotChat } from "../lib/telegram";
import type { MusicRequest } from "./api";

interface AddViewProps {
  requests: MusicRequest[];
  onRequest: () => void;
}

const STEPS = [
  { Icon: MessageCircle, title: "Ботты ашыңыз", text: "Төмендегі батырма бот чатын ашады." },
  { Icon: Forward, title: "Әнді жіберіңіз", text: "Кез келген каналдан не чаттан әнді ботқа қайта жіберіңіз (forward) немесе телефоннан «Музыка» ретінде жүктеңіз. Бірден бірнешеуін де болады." },
  { Icon: Sparkles, title: "Дайын!", text: "Ән бірден каталогқа түседі: оны бәрі тыңдай алады, ал сізде «Менің музыкам» бөлімінде тұрады." },
];

export default function AddView({ requests, onRequest }: AddViewProps) {
  return (
    <div className="px-4 pb-6 pt-4">
      <h1 className="text-[26px] font-extrabold tracking-tight text-text">Ән қосу</h1>
      <p className="mt-1 text-[14px] leading-relaxed text-muted">
        Каталогты бәріміз бірге толтырамыз. Сіз қосқан әнді бәрі тыңдай алады.
      </p>

      <ol className="mt-5 space-y-3">
        {STEPS.map(({ Icon, title, text }, index) => (
          <li key={title} className="flex gap-3 rounded-3xl border border-white/5 bg-surface p-4">
            <span className="qm-gradient flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl text-white">
              <Icon size={19} />
            </span>
            <div>
              <p className="text-[15px] font-bold text-text">{index + 1}. {title}</p>
              <p className="mt-0.5 text-[13px] leading-relaxed text-muted">{text}</p>
            </div>
          </li>
        ))}
      </ol>

      <button onClick={() => openBotChat()} className="qm-gradient mt-5 flex w-full items-center justify-center gap-2 rounded-2xl py-3.5 text-[15px] font-bold text-white shadow-[0_10px_30px_rgba(124,58,237,0.35)] active:scale-[0.98]">
        <Send size={18} /> Ботқа ән жіберу
      </button>

      <section className="mt-8">
        <h2 className="flex items-center gap-2 text-[17px] font-extrabold tracking-tight text-text">
          <Music2 size={18} className="text-music" /> Іздеп жүр, бірақ әлі жоқ
        </h2>
        {requests.length ? (
          <ul className="mt-3 divide-y divide-white/5 overflow-hidden rounded-3xl border border-white/5 bg-surface">
            {requests.map((request) => (
              <li key={request.query} className="flex items-center justify-between gap-3 px-4 py-3">
                <span className="min-w-0 truncate text-[14px] text-text">{request.query}</span>
                <span className="shrink-0 rounded-full bg-music/15 px-2.5 py-0.5 text-[12px] font-semibold text-music">
                  {request.votes} адам
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-[13px] text-muted">Әзірге сұраныс жоқ — бәрі табылып жатыр 🎉</p>
        )}
        <button onClick={onRequest} className="mt-3 w-full rounded-2xl bg-elevated py-3 text-[14px] font-semibold text-text active:scale-[0.98]">
          Ән сұрау
        </button>
      </section>
    </div>
  );
}
