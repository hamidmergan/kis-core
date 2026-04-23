export function formatDate(dateStr: string): string {
  return new Date(dateStr.endsWith("Z") ? dateStr : dateStr + "Z").toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Berlin",
  });
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "–";
  if (seconds >= 60) return `${Math.round(seconds / 60)} min`;
  return `${Math.round(seconds)} s`;
}
