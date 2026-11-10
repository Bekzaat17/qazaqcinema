import type { Board } from "../types";

export default function BoardArt({ board }: { board: Board }) {
  if (board.thumbnail)
    return (
      <img
        className="dala-board-art dala-illustration-thumb"
        src={board.thumbnail}
        alt=""
        width="520"
        height="347"
        loading="lazy"
        draggable={false}
      />
    );
  return (
    <div className={`dala-board-art art-${board.biome}`}>
      <span className="dala-art-sun" />
      <i />
      <i />
      <i />
      <b />
      <span className="dala-art-road" />
    </div>
  );
}
