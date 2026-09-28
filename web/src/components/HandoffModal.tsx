// Хэндофф: видео в Mini App не играется, бот уже отправил его в личку. Экран говорит об
// этом и уводит человека в чат — туда, где видео лежит.
//
// Дорога зависит от запуска (`isDirectLaunch`):
//  • из чата бота — кнопка закрывает приложение, и под ним тот самый чат с видео;
//  • прямой ссылкой (сайт, пост канала) — увести в чат мы НЕ можем: клиент игнорирует
//    `openTelegramLink` на чат своего же бота, а закрытие вернёт человека в канал. Поэтому
//    вместо кнопки, которая не сработает, — понятная инструкция: закройте кинотеатр,
//    чат с ботом первый в списке чатов (он только что прислал видео).
//
// ⚠️ Даже `close()` — сообщение по мосту без ответа: часть клиентов его молча игнорирует.
// Экран не верит вызову на слово и через `STUCK_AFTER_MS` СМОТРИТ: если мы всё ещё на
// экране, кнопка меняется на ту же инструкцию. Мёртвой кнопки, на которую жмёшь и ничего
// не происходит, тут быть не должно — это последний шаг воронки.
//
// Исход уходит в метрику (`api.trackHandoff`) с платформой и способом запуска.

import { CircleCheckBig, Loader2, Sparkles, Ticket } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { api } from "../lib/api";
import {
  BOT_USERNAME,
  closeApp,
  getLaunch,
  getPlatform,
  haptic,
  isDirectLaunch,
  setVerticalSwipes,
} from "../lib/telegram";
import Button from "../ui/Button";

/**
 * Сколько ждать реакции клиента, прежде чем убрать кнопку.
 *
 * Секунда с небольшим: меньше — кнопка мигнёт у тех, у кого всё сработало, просто
 * медленно; больше — экран успеет показаться зависшим, а именно этого мы и избегаем.
 */
const STUCK_AFTER_MS = 1100;

/**
 * `idle` — предложили уйти; `leaving` — мост дёрнут, ждём; `guide` — уйти сами не можем
 * (прямой запуск или клиент промолчал), объясняем дорогу словами.
 */
type Stage = "idle" | "leaving" | "guide";

/**
 * `gift` — видео ушло за счёт НЕДЕЛЬНОГО выбора: говорим об этом прямо, одним словом,
 * чтобы человек понял, что неделя началась. Старый одноразовый подарок сюда НЕ попадает
 * (`App` его отсекает): назвать его «апталық таңдау» значило бы соврать.
 * `daily` — это бесплатный фильм дня: выбор цел, и путать одно с другим нельзя, иначе
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
    setStage(isDirectLaunch() ? "guide" : "idle");
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
    const launch = getLaunch();
    void api.trackHandoff("try", platform, launch).catch(() => {});
    closeApp();
    timer.current = window.setTimeout(() => {
      // Страница ушла в фон — значит клиент нас услышал (свернул или открыл чат поверх),
      // и трогать экран, с которого человек уже ушёл, незачем. Возврат разбирает `onResume`.
      if (document.visibilityState !== "visible") return;
      // Без тактильного «внимание»: для человека ничего не сломалось — видео у него есть.
      setStage("guide");
      void api.trackHandoff("stuck", platform, launch).catch(() => {});
    }, STUCK_AFTER_MS);
  }

  function closeGuided(): void {
    haptic.medium();
    void api.trackHandoff("try", getPlatform(), getLaunch()).catch(() => {});
    closeApp();
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
            <Ticket size={30} className="text-brand" />
          ) : daily ? (
            <Sparkles size={30} className="text-brand" />
          ) : (
            <CircleCheckBig size={30} className="text-brand" />
          )}
        </div>
        <h2 id="handoff-title" className="text-xl font-bold text-text">
          {gift
            ? "Апталық таңдауыңыз жіберілді 🎟"
            : daily
              ? "Бүгінгі тегін фильм жіберілді"
              : "Видео ботқа жіберілді"}
        </h2>
        {stage === "guide" ? (
          <ol className="mt-3 space-y-1.5 text-left text-[15px] leading-relaxed text-muted">
            <li>1. Кинотеатрды жабыңыз.</li>
            <li>
              2. Telegram-да <b className="text-text">@{BOT_USERNAME}</b> чатын ашыңыз — ол
              чаттар тізімінің ең басында тұр.
            </li>
            <li>3. Видео сол жерде — ашып қараңыз.</li>
          </ol>
        ) : (
          <p className="mt-2 text-[15px] leading-relaxed text-muted">
            Ботпен чаттан ашып қараңыз. Видео тек сол жерде — қауіпсіздік үшін жүктеп алуға
            болмайды.
          </p>
        )}

        <div className="mt-6 flex flex-col gap-2.5">
          {stage === "guide" ? (
            // Закрыть — единственное, что тут можем сделать мы; чат человек открывает сам.
            <>
              <Button onClick={closeGuided}>Кинотеатрды жабу</Button>
              <Button variant="surface" onClick={onClose}>
                Кинотеатрда қалу
              </Button>
            </>
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
