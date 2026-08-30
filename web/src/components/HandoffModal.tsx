// Хэндофф-модалка (ключевой момент Фазы 9): видео не играется в Mini App — бот отправил
// его в чат. Показываем подтверждение + «Чатқа өту» → переход в чат с ботом.
//
// РЕШЕНИЕ 2026-08-30 (три раунда живых багов подряд, детали — история коммитов):
// 1) Кнопка звала только `WebApp.close()` в расчёте на то, что Telegram сам вернёт на чат, из
//    которого открыли Mini App — ломалось у гостя с Google (direct-link запуск,
//    `t.me/<bot>?startapp=m_<id>`): под Mini App нет чата, close() возвращал на браузер.
// 2) Заменил на `openBotChat()` (`openTelegramLink`) — но с **Bot API 7.0** этот метод САМ
//    БОЛЬШЕ НЕ закрывает Mini App («The Mini App will not be closed after this method is
//    called», core.telegram.org/bots/webapps), плюс `openBotChat()` слал `?start=web` —
//    Telegram шлёт `/start <payload>` заново при КАЖДОМ переходе по такой ссылке, даже если
//    чат уже открыт, так что вместо видео человек видел дефолтное приветствие бота.
//    Убрал payload (см. docstring `openBotChat` в telegram.ts) и добавил явный `close()`.
// 3) Всё ещё ненадёжно — конкретно для Mini App, запущенной direct-link'ом ТОГО ЖЕ бота,
//    `openTelegramLink`/`close()` — задокументированный баг клиента, не нашего кода:
//    github.com/Telegram-Mini-Apps/telegram-apps/issues/326 («does not close app on iOS ...
//    when the mini app was opened from the same url»), issues/743 (методы молчат, хотя
//    isAvailable() = true). Поэтому кнопка теперь настоящая `<a href={BOT_URL}>`: клик по
//    реальной ссылке перехватывают Universal Links/App Links на уровне ОС и клиента Telegram
//    независимо от того, исправен ли конкретно этот метод WebApp SDK на платформе — механизм
//    старше и обкатанней, чем Mini Apps JS-мост. `openBotChat()`+`close()` зовём ДОПОЛНИТЕЛЬНО
//    в onClick (без preventDefault) — где мост исправен, сработает мгновенно; где сломан,
//    сработает сама ссылка.
// 4) С компьютера (Telegram Desktop) заработало, с телефона (нативное приложение) — всё ещё
//    нет: `close()` звался СИНХРОННО, в тот же тик клика по `<a>`. На части мобильных WebView
//    немедленное закрытие/уничтожение контекста обрывает ещё не начавшуюся навигацию по ссылке
//    (классический класс браузерных гонок — сравни с `location.href=…` сразу перед
//    `window.close()`); на Chromium-based Desktop-клиенте это, похоже, проскакивает, на
//    мобильном WebView — нет. Сдвинул `close()` на следующий тик (`setTimeout`), чтобы
//    браузер/WebView успел начать обработку `href` до того, как мы прибьём контекст. Добавил
//    `target="_top"` — на случай, если Mini App рендерится во вложенном фрейме, ссылка обязана
//    всплыть до верхнего уровня, иначе перехват t.me Telegram'ом может не сработать.

import { Clapperboard, Gift, Sparkles } from "lucide-react";

import { BOT_URL, close, openBotChat } from "../lib/telegram";

function goToChat(): void {
  openBotChat();
  // Не синхронно: даём браузеру/WebView шанс начать навигацию по href ДО того, как close()
  // снесёт контекст страницы (см. пункт 4 разбора выше).
  setTimeout(close, 300);
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
          <a
            href={BOT_URL}
            target="_top"
            rel="noopener"
            onClick={goToChat}
            className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-brand px-5 py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-brand/25 transition-transform duration-150 active:scale-[0.98] active:bg-brand-600"
          >
            Чатқа өту
          </a>
        </div>
      </div>
    </div>
  );
}
