export default function Dice({
  value,
  rolling,
}: {
  value: number;
  rolling: boolean;
}) {
  const patterns: Record<number, number[]> = {
    0: [],
    1: [4],
    2: [0, 8],
    3: [0, 4, 8],
    4: [0, 2, 6, 8],
    5: [0, 2, 4, 6, 8],
    6: [0, 2, 3, 5, 6, 8],
  };
  return (
    <span
      className={`dala-die ${rolling ? "rolling" : ""}`}
      aria-label={`Кубик: ${value || "дайын"}`}
    >
      {Array.from({ length: 9 }, (_, i) => (
        <i
          key={i}
          className={(patterns[value] ?? []).includes(i) ? "dot" : ""}
        />
      ))}
    </span>
  );
}
