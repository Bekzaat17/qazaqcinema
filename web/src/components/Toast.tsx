// Мини-тост снизу для ошибок/подтверждений. Сам гаснет.

import { useEffect } from "react";

export default function Toast({ message, onDone }: { message: string; onDone: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDone, 2600);
    return () => clearTimeout(t);
  }, [message, onDone]);

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-[60] flex justify-center pb-[calc(24px+var(--safe-bottom))]">
      <div className="anim-pop rounded-2xl border border-border bg-elevated px-4 py-3 text-sm font-medium text-text shadow-xl">
        {message}
      </div>
    </div>
  );
}
