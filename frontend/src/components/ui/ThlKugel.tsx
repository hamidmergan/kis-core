/** The ball of the THL logo hopping out of its cup, in front of the chat waiting line. */
export default function ThlKugel({ height = 18 }: { height?: number }) {
  return (
    <svg height={height} width={(height * 50) / 80} viewBox="418 84 50 80" aria-hidden="true" style={{ display: "block", flexShrink: 0, overflow: "visible" }}>
      <path
        transform="translate(498.9941 188.0049)"
        d="M-35.9-66.7c0,0-4.1,32.6-20.1,32.6s-20.1-32.6-20.1-32.6s-2.4,19.4,0.3,39.9h19.7h0.2h0.2H-36C-33.5-47.3-35.9-66.7-35.9-66.7"
        fill="var(--foreground)"
      />
      <circle
        cx="442.95"
        cy="124"
        r="18.5"
        fill="var(--thl-rot)"
        style={{ animation: "thl-kugel 1.4s ease-in-out infinite", transformOrigin: "442.95px 142.5px" }}
      />
    </svg>
  );
}
