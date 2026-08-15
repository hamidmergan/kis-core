function intlTag(locale: string): string {
  return locale === "en" ? "en-GB" : "de-DE";
}

/** Backend timestamps carry no zone marker but are UTC. */
export function toMs(dateStr: string): number {
  return new Date(dateStr.endsWith("Z") ? dateStr : dateStr + "Z").getTime();
}

export function formatDate(dateStr: string, locale: string = "de"): string {
  return new Date(toMs(dateStr)).toLocaleString(intlTag(locale), {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Berlin",
  });
}

export function formatDuration(seconds: number | null | undefined, locale: string = "de"): string {
  if (seconds == null) return "-";
  const minLabel = locale === "en" ? "min" : "min";
  const secLabel = locale === "en" ? "s" : "s";
  if (seconds >= 60) return `${Math.round(seconds / 60)} ${minLabel}`;
  return `${Math.round(seconds)} ${secLabel}`;
}

/** How the three shapes of an elapsed span get spelled out. */
export type ElapsedFormatter = {
  seconds: (n: number) => string;
  minutes: (m: number, s: string) => string;
  hours: (h: number, m: string, s: string) => string;
};

/**
 * Split a span in milliseconds into seconds, m:ss or h:mm:ss and let the caller
 * spell it. The job list wants bare "2:07", the job detail wants translated
 * words, so only the splitting is shared.
 */
export function formatElapsed(ms: number, fmt: ElapsedFormatter): string {
  const totalSec = Math.round(ms / 1000);
  if (totalSec < 60) return fmt.seconds(totalSec);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  if (h > 0) return fmt.hours(h, String(m).padStart(2, "0"), String(s).padStart(2, "0"));
  return fmt.minutes(m, String(s).padStart(2, "0"));
}
