// Хэндофф-модалка (ключевой момент Фазы 9): видео не играется в Mini App — бот отправил
// его в чат. Показываем подтверждение + «Чатқа өту» → openBotChat().
//
// РЕШЕНИЕ 2026-08-30: раньше кнопка звала WebApp.close() в расчёте на то, что Telegram сам
// вернёт на чат, из которого открыли Mini App. Это верно только когда Mini App и правда была
// открыта ИЗ чата с ботом. У гостя с Google (SEO-страница → `t.me/<bot>?startapp=m_<id>`)
// под Mini App нет чата — это отдельный direct-link запуск, и close() просто гасит окно,
// возвращая на браузер/системный экран, а не в чат с присланным видео: кнопка выглядела
// нерабочей. `openBotChat()` (тот же приём, что в `BotStartSheet`) не полагается на то, что
// было «под низом» — активно открывает чат через `openTelegramLink`, который сам сворачивает
// Mini App, работает из любого места запуска одинаково.

import { Clapperboard, Gift, Sparkles } from "lucide-react";

import Button from "../ui/Button";
import { openBotChat } from "../lib/telegram";

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
          <Button onClick={() => openBotChat()}>Чатқа өту</Button>
        </div>
      </div>
    </div>
  );
}
