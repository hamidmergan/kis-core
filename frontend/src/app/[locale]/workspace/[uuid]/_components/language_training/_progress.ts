/** The percentage in the ring comes ready from the backend. */

export function setProgressPct(set: { progress_pct?: number }): number {
  const pct = set.progress_pct;
  if (typeof pct !== "number" || Number.isNaN(pct)) return 0;
  return Math.min(100, Math.max(0, Math.round(pct)));
}
