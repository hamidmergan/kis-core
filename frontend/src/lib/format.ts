type Locale = "de" | "en";

function intlTag(locale: Locale): string {
  return locale === "en" ? "en-GB" : "de-DE";
}

export function formatDate(dateStr: string, locale: Locale = "de"): string {
  return new Date(dateStr.endsWith("Z") ? dateStr : dateStr + "Z").toLocaleString(intlTag(locale), {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Berlin",
  });
}

export function formatDuration(seconds: number | null | undefined, locale: Locale = "de"): string {
  if (seconds == null) return "-";
  const minLabel = locale === "en" ? "min" : "min";
  const secLabel = locale === "en" ? "s" : "s";
  if (seconds >= 60) return `${Math.round(seconds / 60)} ${minLabel}`;
  return `${Math.round(seconds)} ${secLabel}`;
}
