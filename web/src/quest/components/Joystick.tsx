import { useRef, useState, type PointerEvent } from "react";
import { Move } from "lucide-react";

export default function Joystick({
  onMove,
}: {
  onMove: (x: number, y: number) => void;
}) {
  const pointer = useRef<number | null>(null);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const move = (event: PointerEvent<HTMLDivElement>) => {
    if (pointer.current !== event.pointerId) return;
    const rect = event.currentTarget.getBoundingClientRect();
    let x = event.clientX - rect.left - rect.width / 2,
      y = event.clientY - rect.top - rect.height / 2;
    const distance = Math.hypot(x, y);
    if (distance > 32) {
      x *= 32 / distance;
      y *= 32 / distance;
    }
    setPosition({ x, y });
    onMove(x / 32, y / 32);
  };
  const stop = () => {
    pointer.current = null;
    setPosition({ x: 0, y: 0 });
    onMove(0, 0);
  };
  return (
    <div
      className="quest-joystick"
      aria-label="Қозғалу джойстигі"
      onPointerDown={(event) => {
        pointer.current = event.pointerId;
        event.currentTarget.setPointerCapture(event.pointerId);
        move(event);
      }}
      onPointerMove={move}
      onPointerUp={stop}
      onPointerCancel={stop}
      onLostPointerCapture={stop}
    >
      <div
        className="quest-joystick-knob"
        style={{ transform: `translate(${position.x}px, ${position.y}px)` }}
      >
        <Move size={21} />
      </div>
    </div>
  );
}
