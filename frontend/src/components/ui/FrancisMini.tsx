"use client";

import { BEAK, BEAK_D, EDGE, EYE, WHITE } from "./Francis";

/** Francis' head alone, small enough to sit in front of a text line, moving with the chat phase. */
export default function FrancisMini({ phase, size = 16 }: { phase: "searching" | "generating"; size?: number }) {
  const look = phase === "searching" ? "francis-mini-look 2.4s ease-in-out infinite" : "none";
  const nod = phase === "generating" ? "francis-mini-nod 0.9s ease-in-out infinite" : "none";

  return (
    <svg width={size} height={size} viewBox="34 14 52 52" aria-hidden="true" style={{ display: "block", overflow: "visible", flexShrink: 0 }}>
      <g style={{ animation: nod, transformOrigin: "60px 62px" }}>
        <circle cx="60" cy="40" r="24" fill={WHITE} stroke={EDGE} strokeWidth={2} />
        <path
          d="M53.5 49 Q60 46.8 66.5 49 Q65.5 57.5 60 60.5 Q54.5 57.5 53.5 49 Z"
          fill={BEAK}
          stroke={BEAK_D}
          strokeWidth={1.5}
          strokeLinejoin="round"
        />
        <g style={{ animation: look }}>
          <circle cx="50" cy="39" r="3.6" fill={EYE} />
          <circle cx="70" cy="39" r="3.6" fill={EYE} />
        </g>
      </g>
    </svg>
  );
}
