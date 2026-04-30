"use client";

import { useId } from "react";

export type HildeState = "idle" | "thinking" | "found" | "confused" | "wave";

export interface HildeProps {
  size?: number;
  state?: HildeState;
  className?: string;
}

const KB = "#004261";
const KB_DARK = "#00293d";
const CREAM = "#F5E6CC";
const PEACH = "#F5B181";
const MINT = "#A8D5BA";
const SAND = "#E8DCC4";

export default function Hilde({ size = 120, state = "idle", className }: HildeProps) {
  const reactId = useId();
  const eyeLId = `hilde-eye-l-${reactId}`;
  const eyeRId = `hilde-eye-r-${reactId}`;

  const eyeOffset = state === "thinking" ? -2 : state === "found" ? 2 : 0;
  const pupilSize = state === "thinking" ? 0.3 : state === "confused" ? 1.4 : 1;
  const isWave = state === "wave";

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 120 120"
      className={className}
      style={{ overflow: "visible" }}
    >
      {/* Schatten — pulsiert leicht im Takt des Hops */}
      <ellipse
        cx="60"
        cy="112"
        rx="30"
        ry="3"
        fill={KB}
        opacity="0.12"
        style={{
          animation: isWave ? "hilde-shadow 30s ease-in-out infinite" : "none",
          transformOrigin: "60px 112px",
        }}
      />

      {/* Körper-Gruppe (Hops) — bei Wave: 2 kurze Hops, dann ~28.7s Pause */}
      <g
        style={{
          animation: isWave ? "hilde-bounce 30s ease-in-out infinite" : "none",
          transformOrigin: "60px 108px",
        }}
      >
        {/* Innere Gruppe (Atmen) — läuft in allen States parallel zu sonstigen Animationen */}
        <g
          style={{
            animation: "hilde-breathe 4s ease-in-out infinite",
            transformOrigin: "60px 108px",
          }}
        >
          {/* Körper (rund, leicht oval) */}
          <ellipse cx="60" cy="68" rx="36" ry="40" fill={KB} />

          {/* Bauch-Verlauf (heller Bereich vorne) */}
          <ellipse cx="60" cy="78" rx="24" ry="26" fill={SAND} />

          {/* Streifen am Bauch (Eulen-Federmuster) */}
          <g stroke={KB} strokeWidth="1" fill="none" opacity="0.5">
            <path d="M44 78 Q 50 82, 56 78" />
            <path d="M64 78 Q 70 82, 76 78" />
            <path d="M44 88 Q 50 92, 56 88" />
            <path d="M64 88 Q 70 92, 76 88" />
            <path d="M50 96 Q 56 100, 62 96" />
          </g>

          {/* Ohren */}
          <path d="M30 38 L 36 28 L 42 42 Z" fill={KB} />
          <path d="M90 38 L 84 28 L 78 42 Z" fill={KB} />

          {/* Flügel links — bei Wave leichter Schlag nach außen-unten */}
          <g
            style={{
              transformOrigin: "32px 60px",
              animation: isWave ? "hilde-wing-l 30s ease-in-out infinite" : "none",
            }}
          >
            <ellipse cx="28" cy="74" rx="8" ry="18" fill={KB_DARK} />
          </g>

          {/* Flügel rechts — bei Wave Schlag nach außen-unten, bei found schwenkt er alle 30s zur Lupe */}
          <g
            style={{
              transformOrigin: "88px 60px",
              transform: "rotate(0deg)",
              transition: "transform .3s ease",
              animation: isWave
                ? "hilde-wing-r 30s ease-in-out infinite"
                : state === "found"
                  ? "hilde-wing-found 30s ease-in-out infinite"
                  : "none",
            }}
          >
            <ellipse cx="92" cy="74" rx="8" ry="18" fill={KB_DARK} />
          </g>

          {/* Clip-Pfade für die Augenringe — damit Lider nur im Auge sichtbar sind */}
          <defs>
            <clipPath id={eyeLId}>
              <circle cx="48" cy="58" r="12.5" />
            </clipPath>
            <clipPath id={eyeRId}>
              <circle cx="72" cy="58" r="12.5" />
            </clipPath>
          </defs>

          {/* Augenringe (typisch Eule) */}
          <circle cx="48" cy="58" r="13" fill={CREAM} />
          <circle cx="72" cy="58" r="13" fill={CREAM} />
          <circle cx="48" cy="58" r="13" fill="none" stroke={KB} strokeWidth="1.5" />
          <circle cx="72" cy="58" r="13" fill="none" stroke={KB} strokeWidth="1.5" />

          {/* Augen */}
          {state === "thinking" ? (
            <>
              {/* Pupillen wandern beim Denken nach oben links und leicht hin & her */}
              <g
                style={{
                  animation: "hilde-think-eyes 3.2s ease-in-out infinite",
                  transformOrigin: "60px 58px",
                }}
              >
                <circle cx={48} cy="55" r="4" fill="#1a1a1a" />
                <circle cx={72} cy="55" r="4" fill="#1a1a1a" />
                <circle cx={49} cy="53.5" r="1.2" fill="#fff" />
                <circle cx={73} cy="53.5" r="1.2" fill="#fff" />
              </g>
            </>
          ) : (
            <>
              {/* Pupillen + Glanzpunkte — wandern im Idle */}
              <g
                style={{
                  animation:
                    state === "idle" ? "hilde-eyes-look 7s ease-in-out infinite" : "none",
                  transformOrigin: "60px 58px",
                }}
              >
                <circle cx={48 + eyeOffset} cy="58" r={4 * pupilSize} fill="#1a1a1a" />
                <circle cx={72 + eyeOffset} cy="58" r={4 * pupilSize} fill="#1a1a1a" />
                <circle cx={49 + eyeOffset} cy="56.5" r="1.2" fill="#fff" />
                <circle cx={73 + eyeOffset} cy="56.5" r="1.2" fill="#fff" />
              </g>

              {/* Augenlider — ortsfest, geclippt auf den Augenring (wandern NICHT mit) */}
              {state === "confused" ? (
                <>
                  <g clipPath={`url(#${eyeLId})`}>
                    <rect
                      x="35"
                      y="45"
                      width="26"
                      height="13"
                      fill={KB}
                      style={{
                        transformOrigin: "48px 45px",
                        animation: "hilde-confused-top 30s ease-in-out infinite",
                      }}
                    />
                    <rect
                      x="35"
                      y="58"
                      width="26"
                      height="13"
                      fill={KB}
                      style={{
                        transformOrigin: "48px 71px",
                        animation: "hilde-confused-bottom 30s ease-in-out infinite",
                      }}
                    />
                  </g>
                  <g clipPath={`url(#${eyeRId})`}>
                    <rect
                      x="59"
                      y="45"
                      width="26"
                      height="13"
                      fill={KB}
                      style={{
                        transformOrigin: "72px 45px",
                        animation: "hilde-confused-top 30s ease-in-out infinite",
                      }}
                    />
                    <rect
                      x="59"
                      y="58"
                      width="26"
                      height="13"
                      fill={KB}
                      style={{
                        transformOrigin: "72px 71px",
                        animation: "hilde-confused-bottom 30s ease-in-out infinite",
                      }}
                    />
                  </g>
                </>
              ) : (
                <>
                  {/* Linkes Auge: oberes & unteres Lid — nur innerhalb des Augenrings sichtbar */}
                  <g clipPath={`url(#${eyeLId})`}>
                    <rect
                      x="35"
                      y="45"
                      width="26"
                      height="13"
                      fill={KB}
                      style={{ animation: "hilde-blink-top 20s ease-in-out infinite" }}
                    />
                    <rect
                      x="35"
                      y="58"
                      width="26"
                      height="13"
                      fill={KB}
                      style={{ animation: "hilde-blink-bottom 20s ease-in-out infinite" }}
                    />
                  </g>
                  {/* Rechtes Auge: oberes & unteres Lid */}
                  <g clipPath={`url(#${eyeRId})`}>
                    <rect
                      x="59"
                      y="45"
                      width="26"
                      height="13"
                      fill={KB}
                      style={{ animation: "hilde-blink-top 20s ease-in-out infinite" }}
                    />
                    <rect
                      x="59"
                      y="58"
                      width="26"
                      height="13"
                      fill={KB}
                      style={{ animation: "hilde-blink-bottom 20s ease-in-out infinite" }}
                    />
                  </g>
                </>
              )}
            </>
          )}

          {/* Brille (Akademiker-Akzent!) */}
          <line x1="61" y1="58" x2="59" y2="58" stroke={KB_DARK} strokeWidth="1.5" />

          {/* Schnabel */}
          <path d="M56 70 L 60 76 L 64 70 Z" fill={PEACH} />

          {/* Brauen (nur confused) */}
          {state === "confused" && (
            <>
              <path
                d="M40 44 L 56 48"
                stroke={KB_DARK}
                strokeWidth="2"
                strokeLinecap="round"
              />
              <path
                d="M64 48 L 80 44"
                stroke={KB_DARK}
                strokeWidth="2"
                strokeLinecap="round"
              />
            </>
          )}

          {/* Found: Lupe — sitzt in Standard-Pose, alle 30s wandert sie hoch zum Auge */}
          {state === "found" && (
            <g transform="translate(82 70) rotate(15)">
              <g style={{ animation: "hilde-magnify 30s ease-in-out infinite" }}>
                <circle cx="0" cy="0" r="6" fill="none" stroke={KB_DARK} strokeWidth="1.8" />
                <circle cx="0" cy="0" r="6" fill={MINT} opacity="0.4" />
                <line
                  x1="4"
                  y1="4"
                  x2="9"
                  y2="9"
                  stroke={KB_DARK}
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </g>
            </g>
          )}

          {/* Thinking: Sprechblase mit animierten „...“ (wie Tipp-Indikator) */}
          {state === "thinking" && (
            <g>
              <rect x="90" y="10" width="30" height="20" rx="10" fill="#fff" stroke={KB} strokeWidth="1.2" />
              <circle
                cx="99"
                cy="20"
                r="1.8"
                fill={KB}
                style={{
                  transformOrigin: "99px 20px",
                  animation: "hilde-think-dot 1.4s ease-in-out infinite",
                  animationDelay: "0s",
                }}
              />
              <circle
                cx="105"
                cy="20"
                r="1.8"
                fill={KB}
                style={{
                  transformOrigin: "105px 20px",
                  animation: "hilde-think-dot 1.4s ease-in-out infinite",
                  animationDelay: "0.2s",
                }}
              />
              <circle
                cx="111"
                cy="20"
                r="1.8"
                fill={KB}
                style={{
                  transformOrigin: "111px 20px",
                  animation: "hilde-think-dot 1.4s ease-in-out infinite",
                  animationDelay: "0.4s",
                }}
              />
            </g>
          )}

          {/* Füße */}
          <path
            d="M50 108 L 50 113 M48 113 L 52 113"
            stroke={PEACH}
            strokeWidth="2"
            strokeLinecap="round"
          />
          <path
            d="M70 108 L 70 113 M68 113 L 72 113"
            stroke={PEACH}
            strokeWidth="2"
            strokeLinecap="round"
          />
        </g>
        {/* Ende Atmen-Gruppe */}
      </g>
      {/* Ende Körper-Gruppe */}

      {/* Confused: Fragezeichen — ortsfest, atmet NICHT mit */}
      {state === "confused" && (
        <text x="94" y="30" fontSize="18" fontWeight="700" fill={KB} fontFamily="Geist, system-ui">
          ?
        </text>
      )}
    </svg>
  );
}
