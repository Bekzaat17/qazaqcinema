import { useId, useState, type SVGProps } from "react";

export type Portrait = "male" | "female";
export interface PlayerAppearance { avatar_url?: string; portrait?: Portrait }

export default function PlayerAvatar({ appearance, color = "#3d8bff", size = 44, ...props }:
  SVGProps<SVGSVGElement> & { appearance?: PlayerAppearance; color?: string; size?: number }) {
  const id = useId().replace(/:/g, "");
  const [failed, setFailed] = useState("");
  const photo = appearance?.avatar_url;
  const female = appearance?.portrait === "female";
  return <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" {...props}>
    <defs><clipPath id={`face-${id}`}><circle cx="32" cy="32" r="30" /></clipPath></defs>
    <circle cx="32" cy="32" r="31" fill="#fff9e9" />
    <g clipPath={`url(#face-${id})`}>
      <circle cx="32" cy="32" r="30" fill={color} />
      <circle cx="22" cy="17" r="28" fill="#fff" opacity=".15" />
      {female && <path d="M14 32q-3-24 18-25 22 1 18 27l3 16H11Z" fill="#423333" />}
      <path d="M9 65q1-20 23-21 22 1 23 21" fill={female ? "#f3dcad" : "#254c61"} />
      <path d="M26 39v10q6 5 12 0V39" fill="#d9a779" />
      <ellipse cx="32" cy="29" rx="14" ry="17" fill="#f0c79f" />
      {female ? <path d="M16 27q-3-20 16-21 18 0 17 22-8-5-13-14-7 11-20 13" fill="#423333" />
        : <path d="M17 28q-4-23 16-22 18-1 15 22l-5-10q-17 5-21-1Z" fill="#3f3430" />}
      <path d="M25 28h2m10 0h2" stroke="#4d3830" strokeWidth="2.4" strokeLinecap="round" />
      <path d="M28 37q4 4 8 0" fill="none" stroke="#9b5948" strokeWidth="1.7" strokeLinecap="round" />
      <path d="m24 48 8 7 8-7" fill="none" stroke={female ? "#a77c4f" : "#70b7c4"} strokeWidth="2" />
      {photo && failed !== photo && <image href={photo} width="64" height="64"
        preserveAspectRatio="xMidYMid slice" onError={() => setFailed(photo)} />}
    </g>
    <circle cx="32" cy="32" r="30" fill="none" stroke="#fff7df" strokeWidth="2" />
  </svg>;
}
