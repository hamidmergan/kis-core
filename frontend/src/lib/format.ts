function intlTag(locale: string): string {
  return locale === "en" ? "en-GB" : "de-DE";
}

// Most backend timestamps carry no zone marker but are UTC; a few (timestamptz columns) already carry an offset.
const HAS_ZONE = /[Zz]|[+-]\d{2}:\d{2}$/;

export function toMs(dateStr: string): number {
  return new Date(HAS_ZONE.test(dateStr) ? dateStr : dateStr + "Z").getTime();
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

/** Splits a duration, the caller does the labelling. */
export function formatElapsed(ms: number, fmt: ElapsedFormatter): string {
  const totalSec = Math.round(ms / 1000);
  if (totalSec < 60) return fmt.seconds(totalSec);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  if (h > 0) return fmt.hours(h, String(m).padStart(2, "0"), String(s).padStart(2, "0"));
  return fmt.minutes(m, String(s).padStart(2, "0"));
}

/** A language code written out in the reader's language, the code itself when the browser does not know it. */
export function sprachName(code: string | undefined, locale: string): string | undefined {
  if (!code) return undefined;
  try {
    return new Intl.DisplayNames([locale], { type: "language" }).of(code) ?? code;
  } catch {
    return code;
  }
}
