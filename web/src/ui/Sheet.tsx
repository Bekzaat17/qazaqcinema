// Нижняя шторка (bottom sheet): затемнение + панель, выезжающая снизу.
// Управляется снаружи (open/onClose). Нативную кнопку «назад» Telegram оркестрирует App
// (единая на стек оверлеев), поэтому Sheet сам её не трогает — только фон, Esc-жест по тапу
// и свайп вниз (см. эффект ниже).

import { type ReactNode, useEffect, useRef } from "react";

/** Ниже этого сдвига (px) отпущенный палец считается снапом обратно, а не закрытием. */
const CLOSE_THRESHOLD_PX = 90;

interface SheetProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  /** Уплотнённый режим для модалок по центру не нужен — это всегда низ экрана. */
  labelledBy?: string;
}

export default function Sheet({ open, onClose, children, labelledBy }: SheetProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  // Всегда свежий onClose без пересоздания слушателей на каждый рендер родителя.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  // Блокируем прокрутку фона, пока шторка открыта.
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  // Свайп вниз закрывает шторку. Слушатели нативные (не onTouch* от React) —
  // React вешает touchmove как passive, а preventDefault там нужен по-настоящему,
  // иначе под пальцем вместе со шторкой едет и фон/контент.
  useEffect(() => {
    const panel = panelRef.current;
    const content = contentRef.current;
    if (!open || !panel || !content) return;

    const state = { startY: 0, dy: 0, active: false };

    const onStart = (e: TouchEvent) => {
      // Тянуть можно только когда контент доскроллен до верха — иначе жест должен
      // листать текст описания, а не закрывать карточку.
      if (content.scrollTop > 0) return;
      state.startY = e.touches[0].clientY;
      state.dy = 0;
      state.active = true;
      // Гасим entrance-анимацию: пока она держит transform через fill-mode,
      // инлайновый transform от драга её не перебьёт.
      panel.style.animation = "none";
      panel.style.transition = "none";
    };

    const onMove = (e: TouchEvent) => {
      if (!state.active) return;
      const dy = e.touches[0].clientY - state.startY;
      if (dy <= 0) {
        // Потянули вверх/на месте — это не наш жест, откатываемся и отдаём скролл контенту.
        state.active = false;
        panel.style.transition = "";
        panel.style.transform = "";
        return;
      }
      e.preventDefault();
      state.dy = dy;
      panel.style.transform = `translateY(${dy}px)`;
    };

    const onEnd = () => {
      if (!state.active) return;
      state.active = false;
      if (state.dy > CLOSE_THRESHOLD_PX) {
        onCloseRef.current();
        return;
      }
      panel.style.transition = "transform 0.22s cubic-bezier(0.22, 1, 0.36, 1)";
      panel.style.transform = "";
    };

    panel.addEventListener("touchstart", onStart, { passive: true });
    panel.addEventListener("touchmove", onMove, { passive: false });
    panel.addEventListener("touchend", onEnd);
    panel.addEventListener("touchcancel", onEnd);
    return () => {
      panel.removeEventListener("touchstart", onStart);
      panel.removeEventListener("touchmove", onMove);
      panel.removeEventListener("touchend", onEnd);
      panel.removeEventListener("touchcancel", onEnd);
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center">
      <div className="anim-fade absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        className="anim-sheet relative w-full max-w-md rounded-t-[var(--radius-sheet)] border-t border-border bg-surface pb-[calc(20px+var(--safe-bottom))] shadow-[0_-8px_40px_rgba(0,0,0,0.6)]"
      >
        {/* Хват-полоска */}
        <div className="flex justify-center pt-3 pb-1">
          <span className="h-1.5 w-10 rounded-full bg-elevated" />
        </div>
        <div ref={contentRef} className="max-h-[86vh] overflow-y-auto overscroll-contain">
          {children}
        </div>
      </div>
    </div>
  );
}
