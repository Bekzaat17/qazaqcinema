export default function Equalizer({ paused = false }: { paused?: boolean }) {
  return (
    <span aria-hidden="true" className={`qm-eq flex h-3.5 items-end gap-[2px] text-music ${paused ? "paused" : ""}`}>
      <i style={{ height: "100%" }} />
      <i style={{ height: "100%" }} />
      <i style={{ height: "100%" }} />
    </span>
  );
}
