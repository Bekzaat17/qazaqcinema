import { useEffect, useState } from "react";

// Координаты дорог соответствуют двум иллюстрациям; игровой маршрут не меняется.
const cars = [
  { path: "M208 421H792", color: "#c6a85d", duration: 28, delay: -8 },
  { path: "M792 429H208", color: "#e3e9df", duration: 34, delay: -19 },
  { path: "M208 421H792", color: "#416c72", duration: 28, delay: -23 },
];

function Car({ color }: { color: string }) {
  return <g className="dala-city-car">
    <ellipse cy="2.2" rx="6" ry="2.3" fill="#203e353b" />
    <path d="M-3-2.5v5m6-5v5" stroke="#34423e" strokeWidth="1.5" />
    <rect x="-5.5" y="-2.2" width="11" height="4.4" rx="1.6" fill={color} stroke="#fff6dc" strokeWidth=".35" />
    <path d="M-2.6-1.7H2l1 1.7-1 1.7h-4.6Z" fill="#536c70" />
    <rect x="-1.6" y="-1.55" width="2.4" height="3.1" rx=".4" fill={color} />
    <path d="M4.7-1.5v.8m0 1.4v.8" stroke="#fff0aa" strokeWidth=".8" />
  </g>;
}

export default function CityLife({ biome }: { biome: string }) {
  const [moving, setMoving] = useState(false);
  useEffect(() => {
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setMoving(!document.hidden && !preference.matches);
    update();
    preference.addEventListener("change", update);
    document.addEventListener("visibilitychange", update);
    return () => {
      preference.removeEventListener("change", update);
      document.removeEventListener("visibilitychange", update);
    };
  }, []);
  if (!moving) return null;
  const south = biome === "turkistan" ? 587 : 650;
  const traffic = [...cars,
    { path: `M208 ${south}H792`, color: "#d9bd62", duration: 32, delay: -4 },
    { path: `M792 ${south + 8}H208`, color: "#507b65", duration: 38, delay: -24 },
  ];
  return <g className="dala-city-life" aria-hidden="true" pointerEvents="none">
    {traffic.map((car, i) => <g key={i}>
      <animateMotion path={car.path} dur={`${car.duration}s`} begin={`${car.delay}s`} rotate="auto" repeatCount="indefinite" />
      <Car color={car.color} />
    </g>)}
    {[0, 1, 2, 3, 4, 5].map((i) => <g key={`walker-${i}`}>
      <animateMotion path={i % 2 ? "M483 449L482 482" : "M492 548L491 574L492 618"}
        dur={`${30 + i * 4}s`} begin={`${-i * 8}s`} repeatCount="indefinite" />
      <ellipse cy="2.5" rx="1.5" ry=".7" fill="#314c3638" />
      <path d="M-.5 1.2-.9 3m1.5-1.8.9 3" stroke="#435147" strokeWidth=".6" />
      <path d="M0-.7V1.6" stroke={["#9a5445", "#486f7a", "#d6af62"][i % 3]} strokeWidth="1.8" strokeLinecap="round" />
      <circle cy="-1.5" r=".85" fill="#d7ba8b" />
    </g>)}
    {[0, 1, 2].map((i) => <ellipse key={`ripple-${i}`} cx="490" cy={biome === "turkistan" ? 514 : 518}
      rx="20" ry="7" fill="none" stroke="#eaf9e3" strokeWidth=".65" className="dala-fountain-ripple"
      style={{ animationDelay: `${-i * 1.4}s` }} />)}
    <g className="dala-city-birds">
      <animateMotion path="M240 270Q460 220 720 280" dur="48s" repeatCount="indefinite" />
      {[0, 1, 2].map((i) => <path key={i} d="M-3 1Q-1-2 0 0Q2-2 4 1" fill="none" stroke="#405851" strokeWidth=".8" transform={`translate(${-i * 9} ${i * 5})`} />)}
    </g>
  </g>;
}
