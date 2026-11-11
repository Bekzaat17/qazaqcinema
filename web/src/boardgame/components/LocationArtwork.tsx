import type { Board } from "../types";
import IllustratedBoard from "./IllustratedBoard";
const ignoreAnimation = () => {};

export default function LocationArtwork({ board, onSelect }: { board: Board; onSelect: () => void }) {
  return <div className="dala-location-artwork" aria-label={`${board.name} — 40 ұяшықты классикалық алаң`}>
    <IllustratedBoard board={board} match={null} selected={-1} onSelect={onSelect} onAnimate={ignoreAnimation} />
  </div>;
}
