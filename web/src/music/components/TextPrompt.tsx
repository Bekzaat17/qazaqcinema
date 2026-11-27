// Шторка с одним полем: название плейлиста, переименование, запрос песни.

import { useEffect, useRef, useState } from "react";

import Button from "../../ui/Button";
import Sheet from "../../ui/Sheet";

interface TextPromptProps {
  open: boolean;
  title: string;
  hint?: string;
  placeholder: string;
  initial?: string;
  submitLabel: string;
  maxLength?: number;
  onSubmit: (value: string) => Promise<void> | void;
  onClose: () => void;
}

export default function TextPrompt({ open, title, hint, placeholder, initial = "", submitLabel, maxLength = 64, onSubmit, onClose }: TextPromptProps) {
  const [value, setValue] = useState(initial);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setValue(initial);
    // Фокус после анимации шторки: раньше клавиатура дёргала бы панель.
    const timer = setTimeout(() => inputRef.current?.focus(), 250);
    return () => clearTimeout(timer);
  }, [open, initial]);

  if (!open) return null;
  const submit = async () => {
    if (!value.trim() || busy) return;
    setBusy(true);
    try {
      await onSubmit(value.trim());
    } finally {
      setBusy(false);
    }
  };
  return (
    <Sheet open onClose={onClose} labelledBy="prompt-title">
      <form
        className="px-5 pb-3 pt-1"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <h2 id="prompt-title" className="text-xl font-extrabold tracking-tight text-text">{title}</h2>
        {hint && <p className="mt-1.5 text-[14px] leading-relaxed text-muted">{hint}</p>}
        <input
          ref={inputRef}
          value={value}
          maxLength={maxLength}
          onChange={(event) => setValue(event.target.value)}
          placeholder={placeholder}
          className="mt-4 w-full rounded-2xl border border-border bg-elevated px-4 py-3.5 text-[16px] text-text placeholder:text-faint focus:border-music focus:outline-none"
        />
        <Button type="submit" className="mt-4" loading={busy} disabled={!value.trim()}>
          {submitLabel}
        </Button>
      </form>
    </Sheet>
  );
}
