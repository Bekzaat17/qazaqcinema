// Баннер статуса под шапкой (сейчас — «чек на модерации»).

import { Clock } from "lucide-react";

export default function StatusBanner() {
  return (
    <div className="mx-4 mt-3 flex items-center gap-2.5 rounded-2xl border border-star/25 bg-star/10 px-4 py-3">
      <Clock size={18} className="shrink-0 text-star" />
      <p className="text-sm text-star">Чек тексерілуде — жақын арада хабарласамыз</p>
    </div>
  );
}
