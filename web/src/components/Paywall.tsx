// Пэйволл (bottom sheet): выбор тарифа → способ оплаты. Kaspi первым/акцентным (ручной чек),
// Telegram Stars вторым (мгновенно). Оплата активирует подписку на бэке (Фазы 6–8).

import { ChevronLeft, CreditCard, Check, Copy, ShieldCheck, Star, Upload } from "lucide-react";
import { useMemo, useRef, useState } from "react";

import { ApiError, api, type Movie, type Tariff } from "../lib/api";
import { perDay, tenge } from "../lib/format";
import { haptic, openInvoice } from "../lib/telegram";
import Button from "../ui/Button";
import Sheet from "../ui/Sheet";

interface PaywallProps {
  open: boolean;
  movie: Movie | null;
  tariffs: Tariff[];
  onClose: () => void;
  /** Kaspi: чек принят → уводим юзера в pending_review. */
  onPending: () => void;
  /** Stars: оплата прошла → обновляем доступ. */
  onPaid: () => void;
  onError: (msg: string) => void;
}

export default function Paywall({ open, movie, tariffs, onClose, onPending, onPaid, onError }: PaywallProps) {
  const [selected, setSelected] = useState<string>("");
  const [step, setStep] = useState<"choose" | "kaspi">("choose");
  const [kaspi, setKaspi] = useState<{ number: string; name: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // Тариф по умолчанию — помесячный (recurring), иначе первый.
  const slug = useMemo(() => {
    if (selected) return selected;
    return tariffs.find((t) => t.recurring)?.slug ?? tariffs[0]?.slug ?? "";
  }, [selected, tariffs]);
  const current = tariffs.find((t) => t.slug === slug);

  function reset() {
    setStep("choose");
    setKaspi(null);
    setLoading(false);
    setCopied(false);
  }

  function handleClose() {
    reset();
    onClose();
  }

  async function startKaspi() {
    haptic.medium();
    setLoading(true);
    try {
      const init = await api.initiatePayment(slug, "kaspi");
      setKaspi({ number: init.kaspi_number ?? "", name: init.kaspi_name ?? "" });
      setStep("kaspi");
    } catch {
      onError("Төлемді бастау мүмкін болмады");
    } finally {
      setLoading(false);
    }
  }

  async function startStars() {
    haptic.medium();
    setLoading(true);
    try {
      const init = await api.initiatePayment(slug, "stars");
      if (!init.invoice_url) throw new Error("no invoice");
      const status = await openInvoice(init.invoice_url);
      if (status === "paid") {
        haptic.success();
        reset();
        onPaid();
      } else if (status === "failed") {
        onError("Төлем өтпеді");
      }
      // cancelled/pending — тихо
    } catch {
      onError("Stars төлемін ашу мүмкін болмады");
    } finally {
      setLoading(false);
    }
  }

  async function uploadProof(file: File) {
    setLoading(true);
    try {
      await api.submitProof(slug, file);
      haptic.success();
      reset();
      onPending();
    } catch (e) {
      const msg = e instanceof ApiError && e.status === 413 ? "Файл тым үлкен" : "Чекті жіберу мүмкін болмады";
      onError(msg);
    } finally {
      setLoading(false);
    }
  }

  async function copyNumber() {
    if (!kaspi) return;
    try {
      await navigator.clipboard.writeText(kaspi.number.replace(/\s/g, ""));
      setCopied(true);
      haptic.success();
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard недоступен — номер и так на экране */
    }
  }

  return (
    <Sheet open={open} onClose={handleClose} labelledBy="paywall-title">
      <div className="px-5 pb-3 pt-1">
        {step === "choose" ? (
          <>
            <h2 id="paywall-title" className="text-xl font-extrabold tracking-tight text-text">
              {movie ? `«${movie.title_kk}» көру үшін` : "Жазылым рәсімдеу"}
            </h2>
            <p className="mt-1 text-sm text-muted">Тарифті таңдап, төлеу тәсілін таңдаңыз.</p>

            <div className="mt-4 flex flex-col gap-2.5">
              {tariffs.map((t) => (
                <TariffCard key={t.slug} tariff={t} active={t.slug === slug} onSelect={() => {
                  haptic.select();
                  setSelected(t.slug);
                }} />
              ))}
            </div>

            <div className="mt-5 flex flex-col gap-2.5">
              <Button variant="kaspi" loading={loading} onClick={startKaspi}>
                <CreditCard size={18} />
                Kaspi арқылы төлеу
              </Button>
              <Button variant="stars" loading={loading} onClick={startStars}>
                <Star size={17} className="fill-star" />
                Telegram Stars {current ? `· ${current.price_xtr}` : ""}
              </Button>
            </div>
            <p className="mt-3 flex items-center justify-center gap-1.5 text-xs text-faint">
              <ShieldCheck size={13} />
              Kaspi — 10–15 мин ішінде тексереміз · Stars — бірден
            </p>
          </>
        ) : (
          <KaspiStep
            kaspi={kaspi}
            amount={current ? tenge(current.price_kzt) : ""}
            copied={copied}
            loading={loading}
            onCopy={copyNumber}
            onBack={() => setStep("choose")}
            onPick={() => fileRef.current?.click()}
          />
        )}
      </div>

      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) void uploadProof(file);
        }}
      />
    </Sheet>
  );
}

function TariffCard({ tariff, active, onSelect }: { tariff: Tariff; active: boolean; onSelect: () => void }) {
  const best = tariff.days >= 30;
  return (
    <button
      onClick={onSelect}
      className={`relative flex items-center justify-between rounded-2xl border p-4 text-left transition-colors ${
        active ? "border-brand bg-brand/10" : "border-border bg-elevated"
      }`}
    >
      <div>
        <p className="font-semibold text-text">{tariff.title_kk}</p>
        {best && <p className="mt-0.5 text-xs text-brand">{perDay(tariff.price_kzt, tariff.days)}</p>}
      </div>
      <div className="flex items-center gap-3">
        <span className="text-lg font-bold text-text tabular">{tenge(tariff.price_kzt)}</span>
        <span
          className={`flex h-5 w-5 items-center justify-center rounded-full border-2 ${
            active ? "border-brand bg-brand" : "border-faint"
          }`}
        >
          {active && <Check size={12} className="text-white" strokeWidth={3} />}
        </span>
      </div>
      {best && (
        <span className="absolute -top-2 right-4 rounded-full bg-brand px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
          Ең тиімді
        </span>
      )}
    </button>
  );
}

function KaspiStep({
  kaspi,
  amount,
  copied,
  loading,
  onCopy,
  onBack,
  onPick,
}: {
  kaspi: { number: string; name: string } | null;
  amount: string;
  copied: boolean;
  loading: boolean;
  onCopy: () => void;
  onBack: () => void;
  onPick: () => void;
}) {
  return (
    <>
      <button onClick={onBack} className="mb-1 -ml-1 flex items-center gap-1 text-sm text-muted active:text-text">
        <ChevronLeft size={18} />
        Артқа
      </button>
      <h2 className="text-xl font-extrabold tracking-tight text-text">Kaspi аудару</h2>
      <p className="mt-1 text-sm text-muted">
        Төмендегі нөмірге <span className="font-semibold text-text">{amount}</span> аударыңыз да, чектің
        скриншотын жүктеңіз.
      </p>

      <div className="mt-4 rounded-2xl border border-border bg-elevated p-4">
        <p className="text-xs text-faint">Kaspi нөмірі</p>
        <div className="mt-1 flex items-center justify-between gap-3">
          <span className="text-lg font-bold text-text tabular">{kaspi?.number}</span>
          <button
            onClick={onCopy}
            className="flex items-center gap-1.5 rounded-xl border border-border bg-surface px-3 py-1.5 text-sm font-medium text-brand active:bg-surface-2"
          >
            {copied ? <Check size={15} /> : <Copy size={15} />}
            {copied ? "Көшірілді" : "Көшіру"}
          </button>
        </div>
        {kaspi?.name && (
          <>
            <p className="mt-3 text-xs text-faint">Алушы</p>
            <p className="mt-0.5 font-medium text-text">{kaspi.name}</p>
          </>
        )}
      </div>

      <div className="mt-5">
        <Button loading={loading} onClick={onPick}>
          <Upload size={18} />
          Чекті жүктеу
        </Button>
      </div>
    </>
  );
}
