import type { Board } from "../types";

export default function LocationArtwork({
  board,
  onSelect,
}: {
  board: Board;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      className="dala-location-artwork"
      aria-label={`${board.name} — ойынды таңдау`}
      onClick={onSelect}
    >
      <img
        src={board.illustration}
        alt={board.name}
        width="1536"
        height="1024"
        fetchPriority="high"
        draggable={false}
      />
      <span className="dala-location-caption">
        {board.name}
        <small>Өлкені зертте · Партияны таңда</small>
      </span>
    </button>
  );
}
