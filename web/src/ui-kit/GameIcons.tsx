import { useId, type SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

export function GameCoin({ size = 20, ...props }: IconProps) {
  const id = useId().replace(/:/g, "");
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true" {...props}>
    <defs><linearGradient id={`coin-${id}`} x1="5" y1="3" x2="19" y2="22" gradientUnits="userSpaceOnUse">
      <stop stopColor="#ffe9a0" /><stop offset=".5" stopColor="#eac15f" /><stop offset="1" stopColor="#b77a2f" />
    </linearGradient></defs>
    <circle cx="12" cy="12" r="10" fill={`url(#coin-${id})`} stroke="#a56f2d" strokeWidth="1.2" />
    <circle cx="12" cy="12" r="7.6" stroke="#fff0bb" strokeWidth=".8" />
    <path d="m12 6 4.5 6-4.5 6-4.5-6Z" fill="#9c6628" />
    <path d="m12 6 4.5 6H12Z" fill="#fff2bd" />
  </svg>;
}

export function YurtIcon({ size = 20, ...props }: IconProps) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
    <path d="M3 12c1-3 4.5-6 9-7 4.5 1 8 4 9 7v8H3Z" />
    <path d="M3 12c5 2 13 2 18 0M10 20v-5h4v5M10 5V3h4v2M7 14v4m10-4v4" />
  </svg>;
}

export function WellIcon({ size = 20, ...props }: IconProps) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
    <path d="m3 7 9-5 9 5H3Zm3 0v9m12-9v9M12 7v7m-3 0h6v4H9Z" />
    <path d="M4 16v5c5 2 11 2 16 0v-5M4 16c5 2 11 2 16 0" />
  </svg>;
}
