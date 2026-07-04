// Нижняя шторка (bottom sheet): затемнение + панель, выезжающая снизу.
// Управляется снаружи (open/onClose). Нативную кнопку «назад» Telegram оркестрирует App
// (единая на стек оверлеев), поэтому Sheet сам её не трогает — только фон и Esc-жест по тапу.

import { type ReactNode, useEffect } from "react";

interface SheetProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  /** Уплотнённый режим для модалок по центру не нужен — это всегда низ экрана. */
  labelledBy?: string;
}

export default function Sheet({ open, onClose, children, labelledBy }: SheetProps) {
  // Блокируем прокрутку фона, пока шторка открыта.
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center">
      <div className="anim-fade absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        className="anim-sheet relative w-full max-w-md rounded-t-[var(--radius-sheet)] border-t border-border bg-surface pb-[calc(20px+var(--safe-bottom))] shadow-[0_-8px_40px_rgba(0,0,0,0.6)]"
      >
        {/* Хват-полоска */}
        <div className="flex justify-center pt-3 pb-1">
          <span className="h-1.5 w-10 rounded-full bg-elevated" />
        </div>
        <div className="max-h-[86vh] overflow-y-auto overscroll-contain">{children}</div>
      </div>
    </div>
  );
}
