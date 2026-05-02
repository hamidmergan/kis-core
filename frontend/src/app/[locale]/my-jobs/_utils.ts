type DurationFormatter = {
  seconds: (n: number) => string;
  minutes: (m: number, s: string) => string;
  hours: (h: number, m: string, s: string) => string;
};


export function formatDate(dateStr: string, locale: string = "de"): string {
  const tag = locale === "en" ? "en-US" : "de-DE";
  return new Date(dateStr.endsWith("Z") ? dateStr : dateStr + "Z").toLocaleString(tag, {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin",
  });
}


export function formatDuration(ms: number, fmt: DurationFormatter): string {
  const totalSec = Math.round(ms / 1000);
  if (totalSec < 60) return fmt.seconds(totalSec);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  if (h > 0) return fmt.hours(h, String(m).padStart(2, "0"), String(s).padStart(2, "0"));
  return fmt.minutes(m, String(s).padStart(2, "0"));
}


export function toMs(dateStr: string): number {
  return new Date(dateStr.endsWith("Z") ? dateStr : dateStr + "Z").getTime();
}
