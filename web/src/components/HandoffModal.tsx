// Хэндофф-модалка (ключевой момент Фазы 9): видео не играется в Mini App — бот отправил
// его в чат. Показываем подтверждение + «Чатқа өту» → openBotChat() + close().
//
// РЕШЕНИЕ 2026-08-30: сначала кнопка звала только WebApp.close() в расчёте на то, что Telegram
// сам вернёт на чат, из которого открыли Mini App — ломалось у гостя с Google (direct-link
// запуск, `t.me/<bot>?startapp=m_<id>`): под Mini App нет чата, close() возвращал на браузер.
// Заменил на openBotChat() (openTelegramLink) — но и этого мало: с **Bot API 7.0** этот метод
// САМ БОЛЬШЕ НЕ закрывает Mini App («The Mini App will not be closed after this method is
// called», core.telegram.org/bots/webapps — до 7.0 закрывал, поведение разъединили). Чат
// открывается, а Mini App остаётся висеть поверх/под ним: на одних клиентах это выглядит как
// «не работает» (приложение всё ещё занимает экран), на других — «открыло, но не закрылось».
// Официальный паттерн после 7.0 — звать оба метода: сперва openTelegramLink, затем close().

import { Clapperboard, Gift, Sparkles } from "lucide-react";

import Button from "../ui/Button";
import { close, openBotChat } from "../lib/telegram";

function goToChat(): void {
  openBotChat();
  close();
}

/**
 * `gift` — видео ушло за счёт подарочного фильма: говорим об этом прямо, одним словом.
 * `daily` — это бесплатный фильм дня: подарок цел, и путать одно с другим нельзя, иначе
 * человек решит, что потратил своё единственное право, и перестанет им пользоваться.
 */
export default function HandoffModal({
  open,
  gift = false,
  daily = false,
}: {
  open: boolean;
  gift?: boolean;
  daily?: boolean;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6">
      <div className="anim-fade absolute inset-0 bg-black/80 backdrop-blur-sm" />
      <div className="anim-pop relative w-full max-w-sm rounded-3xl border border-border bg-surface p-6 text-center shadow-2xl">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-brand/15">
          {gift ? (
            <Gift size={30} className="text-brand" />
          ) : daily ? (
            <Sparkles size={30} className="text-brand" />
          ) : (
            <Clapperboard size={30} className="text-brand" />
          )}
        </div>
        <h2 className="text-xl font-bold text-text">
          {gift
            ? "Сыйлық жіберілді 🎁"
            : daily
              ? "Бүгінгі тегін фильм жіберілді"
              : "Видео ботқа жіберілді"}
        </h2>
        <p className="mt-2 text-[15px] leading-relaxed text-muted">
          Ботпен чаттан ашып қараңыз. Видео тек сол жерде — қауіпсіздік үшін жүктеп алуға болмайды.
        </p>
        <div className="mt-6">
          <Button onClick={goToChat}>Чатқа өту</Button>
        </div>
      </div>
    </div>
  );
}
