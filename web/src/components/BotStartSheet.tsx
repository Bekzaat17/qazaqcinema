// Приглашение открыть чат с ботом — единственный экран, который обязан появиться РАНЬШЕ
// подарка и пэйволла.
//
// Причина техническая, но последствие продуктовое: фильм уходит сообщением в личку, а
// Telegram запрещает боту писать первым. Человек, попавший в Mini App по ссылке (из
// поиска, из браузера, с SEO-страницы), каталог видит — но получить кино не может, пока
// сам не откроет чат. Раньше он узнавал об этом ошибкой ПОСЛЕ нажатия «Көру», уже потратив
// подарок; теперь — одной синей кнопкой до.
//
// Кнопка ведёт в `t.me/<bot>?start=web` через `openTelegramLink`: Telegram сворачивает
// Mini App и открывает чат, где человеку остаётся нажать «Начать». Возврат в приложение
// ловит `visibilitychange` в App — статус перечитывается сам, повторять ничего не нужно.

import { MessageCircle, Play } from "lucide-react";

import { openBotChat } from "../lib/telegram";
import Button from "../ui/Button";
import Sheet from "../ui/Sheet";

interface BotStartSheetProps {
  open: boolean;
  onClose: () => void;
}

export default function BotStartSheet({ open, onClose }: BotStartSheetProps) {
  if (!open) return null;

  return (
    <Sheet open onClose={onClose} labelledBy="botstart-title">
      <div className="px-5 pb-4 pt-1 text-center">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-brand/15">
          <MessageCircle size={30} className="text-brand" />
        </div>
        <h2 id="botstart-title" className="text-xl font-extrabold tracking-tight text-text">
          Ботты іске қосыңыз
        </h2>
        <p className="mt-2 text-[15px] leading-relaxed text-muted">
          Фильм ботпен чатқа жіберіледі. Telegram ботқа бірінші жазуға рұқсат бермейді —
          сондықтан чатты бір рет ашу керек.
        </p>

        <ol className="mt-4 space-y-2 rounded-2xl border border-border bg-elevated p-3 text-left text-[14px] text-muted">
          <li>
            <span className="mr-2 font-bold text-brand">1.</span>
            «Ботты ашу» — чат ашылады
          </li>
          <li>
            <span className="mr-2 font-bold text-brand">2.</span>
            Ботта «Іске қосу» (Start) батырмасын басыңыз
          </li>
          <li>
            <span className="mr-2 font-bold text-brand">3.</span>
            Осында оралыңыз — фильм көруге дайын
          </li>
        </ol>

        <div className="mt-5">
          <Button onClick={() => openBotChat()}>
            <Play size={18} />
            Ботты ашу
          </Button>
          <Button variant="ghost" onClick={onClose} className="mt-1">
            Кейінірек
          </Button>
        </div>
      </div>
    </Sheet>
  );
}
