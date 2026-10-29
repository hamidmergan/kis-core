/** Short fireworks in the brand colours for a completed card, skipped when the system prefers reduced motion. */
export async function fireworks(durationMs = 2500): Promise<void> {
  if (typeof window === "undefined") return;
  // Loaded on demand, the stamp page does not need the library until the last stamp.
  const { default: confetti } = await import("canvas-confetti");
  const css = getComputedStyle(document.documentElement);
  const colors = ["--kb", "--brand-mint", "--brand-red"]
    .map((name) => css.getPropertyValue(name).trim())
    .filter(Boolean)
    .concat("#ffffff");
  const end = Date.now() + durationMs;
  const defaults = { startVelocity: 28, spread: 360, ticks: 55, zIndex: 50, colors, disableForReducedMotion: true };
  const timer = window.setInterval(() => {
    const left = end - Date.now();
    if (left <= 0) {
      window.clearInterval(timer);
      return;
    }
    // Fewer particles towards the end, so the fireworks fade out instead of stopping.
    const particleCount = Math.round(45 * (left / durationMs));
    void confetti({ ...defaults, particleCount, origin: { x: 0.15 + Math.random() * 0.2, y: Math.random() * 0.4 } });
    void confetti({ ...defaults, particleCount, origin: { x: 0.65 + Math.random() * 0.2, y: Math.random() * 0.4 } });
  }, 250);
}
