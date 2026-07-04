// Кнопка с брендовыми вариантами. Иконки (lucide) передаём как children.

import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "kaspi" | "stars" | "ghost" | "surface";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-brand text-white active:bg-brand-600 shadow-lg shadow-brand/25",
  kaspi: "bg-kaspi text-white active:brightness-90 shadow-lg shadow-kaspi/25",
  stars: "bg-elevated text-star border border-star/30 active:bg-surface-2",
  ghost: "bg-transparent text-muted active:bg-elevated",
  surface: "bg-elevated text-text active:bg-surface-2 border border-border",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  loading?: boolean;
  block?: boolean;
  children: ReactNode;
}

export default function Button({
  variant = "primary",
  loading = false,
  block = true,
  disabled,
  className = "",
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 rounded-2xl px-5 py-3.5 text-[15px] font-semibold transition-[transform,background-color,filter] duration-150 active:scale-[0.98] disabled:opacity-50 disabled:active:scale-100 ${
        block ? "w-full" : ""
      } ${VARIANTS[variant]} ${className}`}
    >
      {loading ? <Loader2 size={18} className="animate-spin" /> : children}
    </button>
  );
}
