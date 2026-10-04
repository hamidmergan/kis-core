"use client";

import { useId } from "react";
import type { MascotState } from "./Mascot";

export interface FrancisProps {
  size?: number;
  state?: MascotState;
  className?: string;
}

// Colours taken 1:1 from the reference, do not retune.
export const WHITE = "#FDFCFA";
export const EDGE = "#E7E1D6";
const WING = "#A6AEB2";
const WING_D = "#828D93";
export const BEAK = "#F2A81C";
export const BEAK_D = "#DC9210";
const LEG = "#E7C3AF";
const LEG_D = "#CDA38B";
export const EYE = "#1B1B1B";
const RED = "#D62B2B";
const ACCENT = "#004261";

export default function Francis({ size = 120, state = "idle", className }: FrancisProps) {
  // The colon in React's ids breaks the SVG references.
  const reactId = useId().replace(/[^a-zA-Z0-9]/g, "");
  const shadowId = `francis-shadow-${reactId}`;

  const isWave = state === "wave";
  const isIdle = state === "idle";
  const isFound = state === "found";
  const isThink = state === "thinking";
  const isConf = state === "confused";

  // The head tilts with the mood and stays still while thinking.
  const headAnim = isThink
    ? "none"
    : isConf
      ? "francis-confused-cock 5s ease-in-out infinite"
      : `francis-head-tilt ${isIdle ? "11s" : "18s"} ease-in-out infinite`;

  const foot = (x: number, y: number) => (
    <g>
      <path
        d={`M${x} ${y} L${x - 7} ${y + 6} Q${x} ${y + 7} ${x + 7} ${y + 6} Z`}
        fill={LEG}
        stroke={LEG_D}
        strokeWidth={0.8}
        strokeLinejoin="round"
      />
      <line x1={x - 2.5} y1={y + 1} x2={x - 3.5} y2={y + 6} stroke={LEG_D} strokeWidth={0.7} />
      <line x1={x + 2.5} y1={y + 1} x2={x + 3.5} y2={y + 6} stroke={LEG_D} strokeWidth={0.7} />
    </g>
  );

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 120 120"
      className={className}
      shapeRendering="geometricPrecision"
      style={{ overflow: "visible", display: "block" }}
    >
      <defs>
        <radialGradient id={shadowId} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#2E3C45" stopOpacity={0.32} />
          <stop offset="50%" stopColor="#2E3C45" stopOpacity={0.16} />
          <stop offset="100%" stopColor="#2E3C45" stopOpacity={0} />
        </radialGradient>
      </defs>

      {/* Shadow — shrinks with each hop on wave */}
      <ellipse
        cx="60"
        cy="116.5"
        rx="26"
        ry="4.5"
        fill={`url(#${shadowId})`}
        style={{
          animation: isWave ? "francis-shadow 15s ease-in-out infinite" : "none",
          transformOrigin: "60px 116.5px",
        }}
      />

      {/* Body group (hop animation on wave) */}
      <g
        style={{
          animation: isWave ? "francis-bounce 15s ease-in-out infinite" : "none",
          transformOrigin: "60px 108px",
        }}
      >
        {/* Back parts (breathe): grey back + both wings */}
        <g style={{ animation: "francis-breathe 2s ease-in-out infinite", transformOrigin: "60px 100px" }}>
          <ellipse cx="60" cy="92" rx="33" ry="18" fill={WING} />
          <ellipse cx="60" cy="97" rx="23" ry="11" fill={WING_D} opacity={0.4} />

          {/* Left wing — flaps on wave */}
          <g style={{ transformOrigin: "40px 64px", animation: isWave ? "francis-wing-l 15s ease-in-out infinite" : "none" }}>
            <ellipse cx="30" cy="80" rx="10" ry="19" fill={WING} />
            <ellipse cx="28" cy="90" rx="7" ry="11" fill={WING_D} opacity={0.5} />
          </g>

          {/* Right wing — flaps on wave */}
          <g style={{ transformOrigin: "80px 64px", animation: isWave ? "francis-wing-r 15s ease-in-out infinite" : "none" }}>
            <ellipse cx="90" cy="80" rx="10" ry="19" fill={WING} />
            <ellipse cx="92" cy="90" rx="7" ry="11" fill={WING_D} opacity={0.5} />
          </g>
        </g>

        {/* Legs + webbed feet — static, only hop along with the wave bounce */}
        <g>
          <path d="M54 101 Q51 108 50 112" stroke={LEG} strokeWidth={3.4} fill="none" strokeLinecap="round" />
          <path d="M66 101 Q69 108 70 112" stroke={LEG} strokeWidth={3.4} fill="none" strokeLinecap="round" />
          {foot(50, 112)}
          {foot(70, 112)}
        </g>

        {/* Front parts (breathe): body, lanyard, badge, head */}
        <g style={{ animation: "francis-breathe 2s ease-in-out infinite", transformOrigin: "60px 100px" }}>
          <ellipse cx="60" cy="73" rx="32" ry="37" fill={WHITE} stroke={EDGE} strokeWidth={1} />

          {/* Lanyard — runs behind the head around the neck down to the badge */}
          <path d="M48 57 Q49.5 64 54.5 66 M72 57 Q70.5 64 65.5 66" stroke="#CFC8BB" strokeWidth={1.9} fill="none" strokeLinecap="round" />
          <path d="M48 57 Q49.5 64 54.5 66 M72 57 Q70.5 64 65.5 66" stroke="#fff" strokeWidth={0.9} fill="none" strokeLinecap="round" />

          {/* Red ID badge on the chest */}
          <rect x="52.5" y="65" width="15" height="18" rx="2.5" fill={RED} />

          {/* TH-Lübeck logo (sphere + chalice), drawn white */}
          <g transform="translate(60 74.3) scale(0.247) translate(-442.99 -132.83)">
            <circle cx="442.95" cy="122.26" r="16.2" fill="#fff" />
            <path
              transform="translate(498.9941 188.0049)"
              d="M-35.9-66.7c0,0-4.1,32.6-20.1,32.6s-20.1-32.6-20.1-32.6s-2.4,19.4,0.3,39.9h19.7h0.2h0.2H-36C-33.5-47.3-35.9-66.7-35.9-66.7"
              fill="#fff"
            />
          </g>

          {/* Head group (head + beak + eyes) — tilts depending on state */}
          <g style={{ animation: headAnim, transformOrigin: "60px 60px" }}>
            <circle cx="60" cy="40" r="24" fill={WHITE} stroke={EDGE} strokeWidth={1} />
            <path
              d="M53.5 49 Q60 46.8 66.5 49 Q65.5 57.5 60 60.5 Q54.5 57.5 53.5 49 Z"
              fill={BEAK}
              stroke={BEAK_D}
              strokeWidth={1}
              strokeLinejoin="round"
            />
            <path d="M60 50 L60 59.5" stroke={BEAK_D} strokeWidth={0.8} opacity={0.5} />

            {/* Eyes — blink in all states (~every 15s) */}
            <g style={{ transformOrigin: "60px 39px", animation: "francis-blink 15s ease-in-out infinite" }}>
              {isThink ? (
                <>
                  <circle cx="50" cy="38" r="3" fill={EYE} />
                  <circle cx="70" cy="38" r="3" fill={EYE} />
                  <circle cx="51" cy="36.8" r="1" fill="#fff" />
                  <circle cx="71" cy="36.8" r="1" fill="#fff" />
                </>
              ) : (
                <>
                  <circle cx="50" cy="39" r="3" fill={EYE} />
                  <circle cx="51" cy="37.8" r="1" fill="#fff" />
                  <circle cx="70" cy="39" r="3" fill={EYE} />
                  <circle cx="71" cy="37.8" r="1" fill="#fff" />
                </>
              )}
            </g>
          </g>

        </g>
      </g>

      {/* Found: magnifier — fixed top-right, mirroring the confused question mark */}
      {isFound && (
        <g>
          <circle cx="100" cy="20" r="7" fill="#9FD0E0" opacity={0.4} />
          <circle cx="100" cy="20" r="7" fill="none" stroke="#4A4A4E" strokeWidth={1.8} />
          <line x1="105" y1="25" x2="111" y2="31" stroke="#4A4A4E" strokeWidth={2.2} strokeLinecap="round" />
        </g>
      )}

      {/* Thinking: speech bubble with animated dots — fixed, does not breathe */}
      {isThink && (
        <g>
          <rect x="78" y="-6" width="50" height="32" rx="16" fill="#fff" stroke={ACCENT} strokeWidth={1.6} />
          <circle cx="93" cy="10" r="3" fill={ACCENT} style={{ transformOrigin: "93px 10px", animation: "francis-think-dot 1.4s ease-in-out infinite" }} />
          <circle cx="103" cy="10" r="3" fill={ACCENT} style={{ transformOrigin: "103px 10px", animation: "francis-think-dot 1.4s ease-in-out infinite", animationDelay: "0.2s" }} />
          <circle cx="113" cy="10" r="3" fill={ACCENT} style={{ transformOrigin: "113px 10px", animation: "francis-think-dot 1.4s ease-in-out infinite", animationDelay: "0.4s" }} />
        </g>
      )}

      {/* Confused: question mark — fixed */}
      {isConf && (
        <text x="96" y="28" fontSize="18" fontWeight={700} fill={ACCENT} fontFamily="Geist, system-ui">
          ?
        </text>
      )}
    </svg>
  );
}
