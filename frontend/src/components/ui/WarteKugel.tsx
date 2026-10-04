import type { CSSProperties } from "react";

/** Six dots on a ring around the centre, where the ball bursts to. */
const PUNKTE = [0, 60, 120, 180, 240, 300].map((deg) => {
  const rad = (deg * Math.PI) / 180;
  return { dx: Math.round(Math.cos(rad) * 10), dy: Math.round(Math.sin(rad) * 10) };
});

const MITTE: CSSProperties = { transformBox: "fill-box", transformOrigin: "center" };

/** A ball in the brand colour bursting into dots that turn once clockwise and gather into the ball again. */
export default function WarteKugel({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" style={{ display: "block", flexShrink: 0, overflow: "visible" }}>
      <g style={{ animation: "warte-kugel-drehen 4s ease-in-out infinite", transformOrigin: "12px 12px" }}>
        {PUNKTE.map(({ dx, dy }) => (
          <circle
            key={`${dx}-${dy}`}
            cx="12"
            cy="12"
            r="1.8"
            fill="var(--warte-kugel)"
            style={{ ...MITTE, "--dx": `${dx}px`, "--dy": `${dy}px`, animation: "warte-kugel-punkt 4s ease-in-out infinite" } as CSSProperties}
          />
        ))}
      </g>
      <circle cx="12" cy="12" r="8" fill="var(--warte-kugel)" style={{ ...MITTE, animation: "warte-kugel-ganz 4s ease-in-out infinite" }} />
    </svg>
  );
}
