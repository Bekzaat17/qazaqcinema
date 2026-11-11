import type { Board, Tile } from "../../types";

export function specialSprite(board: Board, tile: Tile): number {
  const index = board.tiles.findIndex((item) => item.id === tile.id);
  if (tile.kind === "station") {
    if (board.biome === "turkistan") return index === 35 || index === 6 ? 14 : 12;
    if (index === 25 || index === 6) return 2;
    return index === 35 ? 3 : index === 15 ? 1 : 0;
  }
  if (tile.kind === "utility") return index === 12 ? 4 : 5;
  return ({ start: 8, chance: 9, community: 10, tax: tile.amount >= 200 ? 11 : 15,
    jail: 6, parking: 7, go_to_jail: 13, rest: 8 } as Record<string, number>)[tile.kind] ?? 9;
}

export default function SpecialMiniature({ board, tile }: { board: Board; tile: Tile }) {
  const sprite = specialSprite(board, tile);
  return <g className="dala-building-miniature dala-special-miniature" pointerEvents="none">
    <svg x="-57" y="-67" width="114" height="100"
      viewBox={`${sprite % 4 * 100} ${Math.floor(sprite / 4) * 100} 100 100`} overflow="hidden">
      <image href="/boardgame/art/city-specials-v1.webp" width="400" height="400" preserveAspectRatio="none" />
    </svg>
  </g>;
}
