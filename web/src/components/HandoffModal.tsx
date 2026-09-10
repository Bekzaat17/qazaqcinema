// Хэндофф: видео в Mini App не играется, бот уже отправил его в личку. Экран говорит об
// этом и уводит человека в чат — туда, где видео лежит.
//
// ⚠️ Увести может только нативный клиент Telegram (`WebApp.close()` / `openTelegramLink`),
// а это сообщения по мосту без ответа и без ошибки: часть клиентов их молча игнорирует —
// особенно у Mini App, запущенной прямой ссылкой того же бота. Проверить вызов нечем,
// поэтому экран не верит ему на слово, а СМОТРИТ на результат: через `STUCK_AFTER_MS`
// приложение либо исчезло с экрана, либо мы всё ещё здесь — и тогда кнопка молча уходит,
// оставляя человека с тем, ради чего экран и открылся: видео в личке, смотреть в чате.
// Мёртвой кнопки, на которую жмёшь и ничего не происходит, тут быть не должно — это
// последний шаг воронки, сразу после того как человек получил фильм.
//
// О самой неудаче не сообщаем. Человеку от неё нет никакой пользы: сделать он всё равно
// может только одно — закрыть приложение и открыть чат, а это и так написано выше.
// Извинения за несработавшую кнопку добавили бы тревоги там, где всё уже хорошо.
//
// Исход уходит в метрику (`api.trackHandoff`) — с разбивкой по платформам видно, где мост
// исправен, а где нет.

import { CircleCheckBig, Gift, Loader2, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { api } from "../lib/api";
import { getPlatform, haptic, leaveToChat, setVerticalSwipes } from "../lib/telegram";
import Button from "../ui/Button";

/**
 * Сколько ждать реакции клиента, прежде чем убрать кнопку.
 *
 * Секунда с небольшим: меньше — кнопка мигнёт у тех, у кого всё сработало, просто
 * медленно; больше — экран успеет показаться зависшим, а именно этого мы и избегаем.
 */
const STUCK_AFTER_MS = 1100;

/** `idle` — предложили уйти; `leaving` — мост дёрнут, ждём; `stuck` — клиент промолчал. */
type Stage = "idle" | "leaving" | "stuck";

/**
 * `gift` — видео ушло за счёт подарочного фильма: говорим об этом прямо, одним словом.
 * `daily` — это бесплатный фильм дня: подарок цел, и путать одно с другим нельзя, иначе
 * человек решит, что потратил своё единственное право, и перестанет им пользоваться.
 */
export default function HandoffModal({
  open,
  gift = false,
  daily = false,
  onClose,
}: {
  open: boolean;
  gift?: boolean;
  daily?: boolean;
  /**
   * Закрыть модалку и остаться в приложении.
   *
   * ⚠️ Обязателен: нативная кнопка «назад» есть не на всех платформах
   * (`useTelegramBackButton` молча ничего не делает, если `BackButton` не отрисовался),
   * и без своей кнопки модалка там становится непроходимой — на последнем шаге
   * сценария, когда видео уже отправлено. Плюс человек, который хочет взять второй
   * фильм, а не идти в чат, визуального выхода не видит вовсе.
   */
  onClose: () => void;
}) {
  const [stage, setStage] = useState<Stage>("idle");
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (!open) return;
    setStage("idle");
    // Пока модалка на экране, свайп вниз снова закрывает Mini App. В каталоге он выключен
    // (иначе протяжка полки сворачивает приложение), а здесь выход — цель экрана, и это
    // ручной путь, который работает даже когда наши методы клиент игнорирует.
    setVerticalSwipes(true);
    return () => {
      setVerticalSwipes(false);
      if (timer.current !== null) clearTimeout(timer.current);
    };
  }, [open]);

  // Блокируем прокрутку каталога под затемнением — как в `Sheet`.
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  function goToChat(): void {
    haptic.medium();
    setStage("leaving");
    const platform = getPlatform();
    void api.trackHandoff("try", platform).catch(() => {});
    leaveToChat();
    timer.current = window.setTimeout(() => {
      // Страница ушла в фон — значит клиент нас услышал (свернул или открыл чат поверх),
      // и трогать экран, с которого человек уже ушёл, незачем. Возврат разбирает `onResume`.
      if (document.visibilityState !== "visible") return;
      // Без тактильного «внимание»: для человека ничего не сломалось — видео у него есть.
      setStage("stuck");
      void api.trackHandoff("stuck", platform).catch(() => {});
    }, STUCK_AFTER_MS);
  }

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6">
      <div
        className="anim-fade absolute inset-0 bg-black/80 backdrop-blur-sm"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="handoff-title"
        className="anim-pop relative w-full max-w-sm rounded-3xl border border-border bg-surface p-6 text-center shadow-2xl"
      >
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-brand/15">
          {gift ? (
            <Gift size={30} className="text-brand" />
          ) : daily ? (
            <Sparkles size={30} className="text-brand" />
          ) : (
            <CircleCheckBig size={30} className="text-brand" />
          )}
        </div>
        <h2 id="handoff-title" className="text-xl font-bold text-text">
          {gift
            ? "Сыйлық жіберілді 🎁"
            : daily
              ? "Бүгінгі тегін фильм жіберілді"
              : "Видео ботқа жіберілді"}
        </h2>
        <p className="mt-2 text-[15px] leading-relaxed text-muted">
          Ботпен чаттан ашып қараңыз. Видео тек сол жерде — қауіпсіздік үшін жүктеп алуға
          болмайды.
        </p>

        <div className="mt-6 flex flex-col gap-2.5">
          {stage === "stuck" ? (
            // Клиент промолчал: предлагать нажать ещё раз нечего, и объясняться не о чем.
            // Одна кнопка НА МЕСТЕ главной — так карточка выглядит законченной, а не
            // потерявшей элемент.
            <Button onClick={onClose}>Түсінікті</Button>
          ) : (
            <>
              <Button onClick={goToChat} disabled={stage === "leaving"}>
                {stage === "leaving" ? (
                  <>
                    <Loader2 size={18} className="animate-spin" />
                    Чат ашылуда…
                  </>
                ) : (
                  "Чатқа өту"
                )}
              </Button>
              {/* Второй, спокойный выход: остаться в кинотеатре. Именно КНОПКОЙ, а не
                  только бэкдропом — на модалке без видимого выхода человек застревает,
                  даже если технически её можно закрыть тапом мимо. */}
              <Button variant="surface" onClick={onClose}>
                Кинотеатрда қалу
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
