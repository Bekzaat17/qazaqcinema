import { useEffect, useRef, useState } from "react";
import type { Match, Move } from "../types";
import PlayerAvatar, { type PlayerAppearance } from "../../ui-kit/PlayerAvatar";
import { playerAppearance } from "../appearance";
import { illustratedPoint, type Point } from "../layout";

export default function PawnLayer({
  match,
  appearances,
  count,
  painted,
  onAnimate,
}: {
  match: Match | null;
  appearances?: Record<string, PlayerAppearance>;
  count: number;
  painted: boolean;
  onAnimate: (active: boolean) => void;
}) {
  const [positions, setPositions] = useState<Point[]>([]),
    previous = useRef<Move[]>([]),
    initial = useRef("");
  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  useEffect(() => {
    const moves = match?.moves ?? [],
      key = match?.players.map((p) => p.id).join(":") ?? "";
    if (!match) {
      setPositions([]);
      previous.current = [];
      initial.current = "";
      onAnimate(false);
      return;
    }
    const final = match.players.map((p) =>
      illustratedPoint(p.position, count, painted),
    );
    if (key !== initial.current || reduced) {
      initial.current = key;
      previous.current = structuredClone(moves);
      setPositions(final);
      onAnimate(false);
      return;
    }
    let overlap = 0;
    for (let n = Math.min(previous.current.length, moves.length); n > 0; n--)
      if (
        JSON.stringify(previous.current.slice(-n)) ===
        JSON.stringify(moves.slice(0, n))
      ) {
        overlap = n;
        break;
      }
    const fresh =
      JSON.stringify(previous.current) === JSON.stringify(moves)
        ? []
        : moves.slice(overlap);
    previous.current = structuredClone(moves);
    if (!fresh.length) {
      setPositions(final);
      onAnimate(false);
      return;
    }
    let frame = 0,
      last = 0,
      elapsed = 0,
      moveIndex = 0;
    const current = match.players.map((p) =>
      illustratedPoint(p.position, count, painted),
    );
    fresh.forEach((move) => {
      current[move.player] = illustratedPoint(move.start, count, painted);
    });
    onAnimate(true);
    const tick = (time: number) => {
      if (document.hidden) {
        setPositions(final);
        onAnimate(false);
        return;
      }
      elapsed += last ? Math.min(time - last, 100) : 0;
      last = time;
      const move = fresh[moveIndex];
      const step = Math.floor(elapsed / 100),
        t = (elapsed % 100) / 100;
      if (step >= move.steps) {
        current[move.player] = illustratedPoint(move.end, count, painted);
        moveIndex++;
        elapsed = 0;
        if (moveIndex >= fresh.length) {
          setPositions(final);
          onAnimate(false);
          return;
        }
      } else {
        const a = illustratedPoint((move.start + step) % count, count, painted),
          b = illustratedPoint((move.start + step + 1) % count, count, painted);
        current[move.player] = {
          x: a.x + (b.x - a.x) * t,
          y: a.y + (b.y - a.y) * t - Math.sin(t * Math.PI) * 10,
        };
      }
      setPositions([...current]);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(frame);
    };
  }, [match, count, onAnimate, reduced, painted]);
  return (
    <g className="dala-svg-pawns" aria-hidden="true">
      {match?.players.map((player, i) => {
        if (player.bankrupt) return null;
        const point =
          positions[i] ?? illustratedPoint(player.position, count, painted);
        return (
          <g
            key={player.id}
            transform={`translate(${point.x + (i % 2 ? 16 : -16)} ${point.y + (i < 2 ? -10 : 18)})`}
          >
            <ellipse cy="8" rx="17" ry="6" fill="#293f44" opacity=".24" />
            <path d="m-5 0 5 9 5-9" fill={player.color} stroke="#fff9e7" strokeWidth="2" />
            <circle cy="-18" r={match.turn === i ? 21 : 18} fill={player.color}
              stroke={match.turn === i ? "#b47e22" : "#fff9e7"} strokeWidth="3" />
            <PlayerAvatar x={-17} y={-35} size={34}
              appearance={playerAppearance(player, appearances)} color={player.color} />
            <circle cx="14" cy="-4" r="7" fill={player.color} stroke="#fff9e7" strokeWidth="1.5" />
            <text x="14" y="-1" textAnchor="middle" fontSize="8" fontWeight="800" fill="#fff">{i + 1}</text>
          </g>
        );
      })}
    </g>
  );
}
