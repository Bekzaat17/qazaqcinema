export default function Brand({ product = "cinema", subtitle, compact = false, mark = true }:
  { product?: "cinema" | "music"; subtitle?: string; compact?: boolean; mark?: boolean }) {
  return (
    <span className={`ui-brand ui-brand--${product} ${compact ? "ui-brand--compact" : ""}`}>
      {mark && <img className="ui-brand-mark" src={product === "music" ? "/logo-music.png" : "/logo-icon.png"} alt="" width={48} height={48} />}
      <span className="ui-brand-copy">
        <span className="ui-brand-name">Qazaq<span>{product === "cinema" ? "Cinema" : "Music"}</span></span>
        {subtitle && <span className="ui-brand-subtitle">{subtitle}</span>}
      </span>
    </span>
  );
}
