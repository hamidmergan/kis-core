export function formatDate(dateStr: string): string {
  return new Date(dateStr.endsWith("Z") ? dateStr : dateStr + "Z").toLocaleString("de-DE", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin",
  });
}


export function formatDuration(ms: number): string {
  const totalSec = Math.round(ms / 1000);
  if (totalSec < 60) return `${totalSec} Sek.`;
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")} Std.`;
  return `${m}:${String(s).padStart(2, "0")} Min.`;
}


export function toMs(dateStr: string): number {
  return new Date(dateStr.endsWith("Z") ? dateStr : dateStr + "Z").getTime();
}
