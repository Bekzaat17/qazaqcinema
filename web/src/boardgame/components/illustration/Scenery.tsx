import type { Board } from "../../types";

export function Tree({
  x = 0,
  y = 0,
  scale = 1,
  apple = false,
}: {
  x?: number;
  y?: number;
  scale?: number;
  apple?: boolean;
}) {
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`}>
      <ellipse cy="5" rx="15" ry="5" fill="#527a6c" opacity=".16" />
      <path d="M-2 0 0-39 4-1" fill="#9f7953" />
      <path
        d="m1-18-12-12 3-2 12 9M2-23l10-12 2 3-10 16"
        stroke="#9b7755"
        strokeWidth="2"
      />
      <ellipse cy="-39" rx="19" ry="21" fill="#5c9275" />
      <ellipse cx="-11" cy="-38" rx="14" ry="16" fill="#76a17b" />
      <ellipse cx="9" cy="-46" rx="13" ry="17" fill="#8db481" />
      <ellipse cx="-3" cy="-52" rx="13" ry="12" fill="#a7c38e" />
      {apple && (
        <g fill="#de8b61">
          <circle cx="-12" cy="-35" r="3" />
          <circle cx="9" cy="-46" r="3" />
          <circle cx="2" cy="-28" r="3" />
        </g>
      )}
    </g>
  );
}
export function Yurt({
  x = 0,
  y = 0,
  scale = 1,
  color = "#ca8663",
}: {
  x?: number;
  y?: number;
  scale?: number;
  color?: string;
}) {
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`}>
      <ellipse cy="6" rx="31" ry="10" fill="#75946c" opacity=".15" />
      <path
        d="M-28-11Q0-3 28-11V9Q0 24-28 9Z"
        fill="#f9ecd0"
        stroke="#d1b787"
        strokeWidth="1.2"
      />
      <path d="M-29-11Q0-49 29-11Q0 6-29-11" fill={color} />
      <path
        d="M-29-11Q0 6 29-11"
        fill="none"
        stroke="#e4bd75"
        strokeWidth="4"
      />
      <ellipse cy="-28" rx="5" ry="2.5" fill="#bd905b" />
      <path d="M-8 14V-3Q0-9 8-3V14" fill="#6b9680" />
      <path
        d="M-25 1q5 7 10 0m30 0q5 7 10 0"
        fill="none"
        stroke="#b58152"
        strokeWidth="1.8"
      />
      <path
        d="M-12-13 0-27 12-13M-22-11-8-24m16 0 14 13"
        fill="none"
        stroke="#e6bb83"
        strokeWidth="1"
        opacity=".75"
      />
    </g>
  );
}
export function Building({
  x = 0,
  y = 0,
  scale = 1,
  color = "#8faaa0",
  hotel = false,
}: {
  x?: number;
  y?: number;
  scale?: number;
  color?: string;
  hotel?: boolean;
}) {
  const height = hotel ? 52 : 30;
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`}>
      <ellipse cy="6" rx="23" ry="7" fill="#648368" opacity=".18" />
      <path d={`M-20 ${-height} 0 ${-height + 9}V8L-20-1Z`} fill="#dfd4b4" />
      <path d={`M0 ${-height + 9} 22 ${-height - 2}V-1L0 8Z`} fill="#f8eacd" />
      <path
        d={`M-24 ${-height} 0 ${-height - 17} 26 ${-height - 2} 0 ${-height + 12}Z`}
        fill={color}
        stroke="#fff5d0"
        strokeWidth="1"
      />
      <path
        d={`M-24 ${-height} 0 ${-height + 12}V${-height + 16}L-24 ${-height + 4}Z`}
        fill="#4c766a"
        opacity=".4"
      />
      <path d="M7 4v-16l8-4V0" fill="#658979" />
      {Array.from({ length: hotel ? 3 : 1 }, (_, i) => (
        <g key={i} fill="#d5b36a" stroke="#efdfaa" strokeWidth=".8">
          <path d={`M-15 ${-height + 10 + i * 13}l6 3v7l-6-3Z`} />
          <path d={`M6 ${-height + 15 + i * 13}l7-3v7l-7 3Z`} />
        </g>
      ))}
      {hotel && (
        <path
          d="M-3-69v-14m0 0 17 4-17 4"
          stroke="#b49b5b"
          strokeWidth="1.3"
          fill="#d6b567"
        />
      )}
    </g>
  );
}
export function Dome({
  x = 0,
  y = 0,
  scale = 1,
}: {
  x?: number;
  y?: number;
  scale?: number;
}) {
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`}>
      <ellipse cy="10" rx="43" ry="11" fill="#a99060" opacity=".15" />
      <path
        d="M-32-26 0-38 34-25V14L0 27-32 14Z"
        fill="#e8cca0"
        stroke="#c9ad7c"
      />
      <path d="M0-38v65l34-13v-39Z" fill="#f4dfb7" />
      <path
        d="M-23-31C-33-62-12-69 0-82 14-70 33-61 25-31Q0-13-23-31"
        fill="#66a5a4"
        stroke="#4c9293"
        strokeWidth="1"
      />
      <path
        d="M0-81q-14 30 0 53m1-53q14 30 0 53"
        fill="none"
        stroke="#a8c5ac"
        strokeWidth="1"
      />
      <path d="M0-82v-12m-3-1 3-4 3 4-3 4Z" stroke="#c6a25f" fill="#d4b56e" />
      <path d="M-9 22V-4Q0-21 9-5V22" fill="#6d9e97" />
      <path d="M-15-2v-8m30 8v-8" stroke="#af8c57" strokeWidth="3" />
      {[-39, 39].map((dx) => (
        <g key={dx} transform={`translate(${dx} 0)`}>
          <path d="M-4 14V-49h8v63" fill="#ead3a4" stroke="#c5ad78" />
          <path d="m-7-50 7-17 7 17Z" fill="#79aaa1" />
          <path d="M-6-35H6" stroke="#c4a36b" strokeWidth="3" />
        </g>
      ))}
    </g>
  );
}
export function Market({
  x = 0,
  y = 0,
  scale = 1,
}: {
  x?: number;
  y?: number;
  scale?: number;
}) {
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`}>
      <path d="M-20-20v31m40-31v31" stroke="#a77d53" strokeWidth="2" />
      <path d="m-25-20 22-14 28 14-22 14Z" fill="#d1ae68" />
      <path
        d="m-25-20 10 3 8-15-6 4m8 15 10 3L12-27l-8-4m12 20 9-9-7-4"
        fill="#f2e2b7"
      />
      <path d="M-20 4 0 13 21 4V-2L0 7-20-2Z" fill="#b89360" />
      <g fill="#c77955">
        <circle cx="-10" cy="0" r="3" />
        <circle cx="-5" cy="2" r="3" />
      </g>
      <g fill="#9eae63">
        <circle cx="5" cy="3" r="3" />
        <circle cx="10" cy="0" r="3" />
      </g>
    </g>
  );
}
function Person({ x, y, color }: { x: number; y: number; color: string }) {
  return (
    <g className="dala-citizen" transform={`translate(${x} ${y})`}>
      <ellipse cy="3" rx="4" ry="1.5" fill="#63816b" opacity=".2" />
      <path d="M-2-6-3 1h6L2-6Z" fill={color} />
      <circle cy="-9" r="2.6" fill="#dbb48c" />
      <path d="M-3-10q3-7 6 0Z" fill={color} />
    </g>
  );
}
export default function Town({ board }: { board: Board }) {
  const apple = board.biome === "almaty";
  return (
    <g aria-hidden="true">
      <path
        d="M500 243 838 418 500 594 162 418Z"
        fill={board.ground}
        stroke="#d6cf9e"
        strokeWidth="4"
      />
      <path
        d="m345 360 303 156m-322-41 325-168"
        stroke="#d8c69f"
        strokeWidth="16"
      />
      <path
        d="m345 360 303 156m-322-41 325-168"
        stroke="#e8ddbb"
        strokeWidth="11"
      />
      <path
        d="M630 365q82 15 70 43t-56 20q-32 7-55-7t8-34q-3-16 33-22"
        fill="#71b6b8"
        stroke="#b6d8b4"
        strokeWidth="5"
      />
      <path
        className="dala-water-line"
        d="m615 392 35 7m-18 11 38-12m-66 9 20 3"
        fill="none"
        stroke="#b6dfd2"
        strokeWidth="2"
      />
      {board.biome === "almaty" && (
        <g>
          <path d="m353 330 57-113 54 99 47-74 72 101" fill="#9bb6b1" />
          <path d="m385 266 25-49 25 47-13-6-13 10-9-11Z" fill="#edf1df" />
          <path d="m489 275 22-33 24 39-14-7-10 7-10-12Z" fill="#f5f3df" />
          <path d="m459 344 48-84 75 90" fill="#b0c6bb" />
          <path d="m492 285 15-25 20 33-13-3-6 7Z" fill="#f3f3dd" />
        </g>
      )}
      {board.biome === "astana" && (
        <g>
          <Building x={595} y={358} scale={1.05} color="#8fbbc0" hotel />
          <Building x={395} y={368} scale={0.75} color="#75a9ac" hotel />
          <g transform="translate(495 340)">
            <ellipse cy="8" rx="28" ry="10" fill="#d6c89c" />
            <path
              d="m-9 2 6-78m12 78L3-76M-15 0l12-76M15 0 3-76"
              stroke="#f5e6bb"
              strokeWidth="3"
            />
            <circle
              cy="-82"
              r="19"
              fill="#d8b261"
              stroke="#efdaa0"
              strokeWidth="3"
            />
            <path
              d="M-15-82h30m-26-9h22m-22 18h22m-11-27q-12 19 0 38m0-38q12 19 0 38"
              fill="none"
              stroke="#bd9951"
              strokeWidth=".8"
            />
          </g>
        </g>
      )}
      {board.biome === "turkistan" && <Dome x={505} y={353} scale={1.05} />}
      {board.biome === "steppe" && (
        <>
          <Yurt x={420} y={363} scale={1} color="#b78157" />
          <Yurt x={526} y={341} scale={0.78} color="#bc8c61" />
          <Yurt x={591} y={366} scale={0.6} color="#8ba38c" />
        </>
      )}
      <Market x={458} y={424} scale={0.7} />
      <Market x={500} y={449} scale={0.66} />
      <Building x={357} y={434} scale={0.65} color="#b88861" />
      <Yurt x={578} y={489} scale={0.65} color="#cb9971" />
      {[
        [312, 394, 0.8],
        [357, 345, 0.72],
        [400, 454, 0.82],
        [429, 489, 0.6],
        [533, 503, 0.62],
        [580, 450, 0.8],
        [720, 421, 0.8],
        [671, 445, 0.65],
        [614, 329, 0.7],
        [547, 394, 0.6],
        [373, 490, 0.6],
        [466, 546, 0.6],
      ].map(([x, y, scale], i) => (
        <Tree key={i} x={x} y={y} scale={scale} apple={apple && i % 2 === 0} />
      ))}
      <path d="m450 507 55 27 55-28-55-28Z" fill="#eaddb4" stroke="#cdbb8c" />
      <text
        x="505"
        y="508"
        textAnchor="middle"
        fill="#8c885d"
        fontSize="10"
        fontWeight="700"
        letterSpacing="2"
      >
        ДАЛА
      </text>
      <text
        x="505"
        y="523"
        textAnchor="middle"
        fill="#8c885d"
        fontSize="10"
        fontWeight="700"
        letterSpacing="2"
      >
        ДӘУЛЕТІ
      </text>
      <g transform="translate(555 418)">
        <path d="m-8 0 16 8m-16-5 16 8" stroke="#967f5b" strokeWidth="2" />
        <path d="m-8 3-1 8m17 0v8" stroke="#8b7659" strokeWidth="1.5" />
      </g>
      <Person x={421} y={412} color="#cb946b" />
      <Person x={550} y={476} color="#6a9e95" />
      <Person x={608} y={436} color="#b18b96" />
      {[
        [367, 398],
        [536, 377],
        [600, 466],
      ].map(([x, y]) => (
        <g key={x} transform={`translate(${x} ${y})`}>
          <path d="M0 0v-21" stroke="#ad9764" strokeWidth="1.5" />
          <path d="m-4-22 4-5 4 5-4 5Z" fill="#e7c879" stroke="#b99750" />
        </g>
      ))}
    </g>
  );
}
