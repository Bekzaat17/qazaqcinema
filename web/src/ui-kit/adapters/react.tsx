import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";
import { Loader2 } from "./icons";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "surface" | "danger" | "kaspi" | "stars";
export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  block?: boolean;
  children: ReactNode;
}

// Публичные компоненты не зависят от классов библиотеки-поставщика.
export function ButtonAdapter({ variant = "primary", size = "md", loading = false,
  block = true, disabled, className = "", children, type = "button", ...rest }: ButtonProps) {
  return <button {...rest} type={type} disabled={disabled || loading}
    aria-busy={loading || undefined}
    className={`ui-button ui-button--${variant} ui-button--${size} ${block ? "ui-button--block" : ""} ${className}`}>
    {loading ? <><Loader2 size={18} className="ui-spinner" aria-hidden="true" />
      <span className="ui-sr-only">Жүктелуде…</span></> : children}
  </button>;
}

export function CardAdapter({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div {...props} className={`ui-card ${className}`} />;
}

export function BadgeAdapter({ tone = "neutral", className = "", ...props }:
  HTMLAttributes<HTMLSpanElement> & { tone?: "neutral" | "brand" | "gold" | "success" }) {
  return <span {...props} className={`ui-badge ui-badge--${tone} ${className}`} />;
}

export function ProgressAdapter({ value, max = 100, label, className = "" }:
  { value: number; max?: number; label: string; className?: string }) {
  const limit = Number.isFinite(max) && max > 0 ? max : 100;
  const current = Number.isFinite(value) ? Math.min(limit, Math.max(0, value)) : 0;
  return <div className={`ui-progress ${className}`} role="progressbar" aria-label={label}
    aria-valuemin={0} aria-valuemax={limit} aria-valuenow={current}>
    <i style={{ width: `${current / limit * 100}%` }} />
  </div>;
}
