export default function Brand({ product = "play", subtitle, compact = false, mark = true }:
  { product?: "cinema" | "play"; subtitle?: string; compact?: boolean; mark?: boolean }) {
  return (
    <span className={`ui-brand ui-brand--${product} ${compact ? "ui-brand--compact" : ""}`}>
      {mark && <img className="ui-brand-mark" src="/logo-icon.png" alt="" width={48} height={48} />}
      <span className="ui-brand-copy">
        <span className="ui-brand-name">Qazaq<span>{product === "cinema" ? "Cinema" : "Play"}</span></span>
        {subtitle && <span className="ui-brand-subtitle">{subtitle}</span>}
      </span>
    </span>
  );
}
