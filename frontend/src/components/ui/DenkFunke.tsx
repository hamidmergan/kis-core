/** Small spark that turns while the assistant is working, in front of the waiting line. */
export default function DenkFunke({ size = 12 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" style={{ display: "block", flexShrink: 0, overflow: "visible" }}>
      <path
        d="M12 0C12 6.6 17.4 12 24 12C17.4 12 12 17.4 12 24C12 17.4 6.6 12 0 12C6.6 12 12 6.6 12 0Z"
        fill="var(--kis-gruen)"
        style={{ animation: "denk-funke 1.6s ease-in-out infinite", transformOrigin: "12px 12px" }}
      />
    </svg>
  );
}
