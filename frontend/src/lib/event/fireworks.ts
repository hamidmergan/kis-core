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
  const shared = { zIndex: 50, colors, disableForReducedMotion: true };

  // Three bursts out of the completion panel, one after the other, like party poppers.
  const panel = document.querySelector('[data-testid="completion"]')?.getBoundingClientRect();
  const origin = panel
    ? { x: (panel.left + panel.width / 2) / window.innerWidth, y: Math.min(0.9, Math.max(0.1, (panel.top + panel.height / 3) / window.innerHeight)) }
    : { x: 0.5, y: 0.35 };
  for (const delay of [0, 450, 900]) {
    window.setTimeout(() => void confetti({ ...shared, particleCount: 110, spread: 80, startVelocity: 35, origin }), delay);
  }

  // Fireworks at both sides for the whole duration, fewer particles towards the end so they fade out.
  const end = Date.now() + durationMs;
  const sides = { ...shared, startVelocity: 28, spread: 360, ticks: 55 };
  const timer = window.setInterval(() => {
    const left = end - Date.now();
    if (left <= 0) {
      window.clearInterval(timer);
      return;
    }
    const particleCount = Math.round(45 * (left / durationMs));
    void confetti({ ...sides, particleCount, origin: { x: 0.15 + Math.random() * 0.2, y: Math.random() * 0.4 } });
    void confetti({ ...sides, particleCount, origin: { x: 0.65 + Math.random() * 0.2, y: Math.random() * 0.4 } });
  }, 250);
}
