/** Today is not an error, hence the accent blue and the same colour as today's grid cell. */
export const URGENCY_TODAY = "var(--kb-dark)";
export const URGENCY_SOON = "var(--warn)";

export function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Colour of the appointment line, blue today and orange under seven days. */
export function urgencyColor(dueDate: string | null | undefined, today: string): string | null {
  if (!dueDate) return null;
  if (dueDate < today) return null;
  if (dueDate === today) return URGENCY_TODAY;
  const days = Math.round(
    (new Date(dueDate).getTime() - new Date(today).getTime()) / 86_400_000,
  );
  if (days > 0 && days < 7) return URGENCY_SOON;
  return null;
}

/** Drops the start time from the description, for spans the end stays. */
/** Drops an 'until' or 'from' carrying its own day, another day stays. */
function stripSelfDate(text: string, dueDate: string | null | undefined): string {
  if (!dueDate || !/^\d{4}-\d{2}-\d{2}$/.test(dueDate)) return text;
  const [jahr, monat, tag] = dueDate.split("-");
  const t = String(Number(tag));
  const m = String(Number(monat));
  // The German date forms with two or four digit years, with and without a leading zero.
  const zahl = `0?${t}\\.\\s*0?${m}\\.\\s*(?:${jahr}|${jahr.slice(2)})`;
  const wort = "(?:bis|ab|until|from)(?:\\s+(?:zum|zur|dem))?";
  return text
    .replace(new RegExp(`\\(?\\s*\\b${wort}\\s+${zahl}\\.?\\s*\\)?`, "gi"), " ")
    .replace(/\s{2,}/g, " ")
    .replace(/^[\s,;.·-]+|[\s,;.·-]+$/g, "")
    .trim();
}

export function cleanScheduleDescription(
  description: string | null | undefined,
  dueTime: string | null | undefined,
  dueDate?: string | null,
): string | null {
  if (!description) return null;
  const trimmed = stripSelfDate(description.trim(), dueDate);
  if (!trimmed) return null;
  if (!dueTime || !/^\d{1,2}:\d{2}$/.test(dueTime)) return trimmed;

  const [hh, mm] = dueTime.split(":");
  const hhInt = String(parseInt(hh, 10));
  const variants = [
    `${hh}:${mm}`,
    `${hhInt}:${mm}`,
    `${hh}\\.${mm}`,
    `${hhInt}\\.${mm}`,
    `${hh}${mm}`,
  ];
  const variantPattern = variants.join("|");
  const hourOnly = hh === hhInt ? hh : `${hh}|${hhInt}`;

  // 1) Whole description is just the due_time (any common spelling) → drop it.
  if (new RegExp(`^(?:um\\s+)?(?:${variantPattern})(?:\\s*Uhr)?\\s*\\.?\\s*$`, "i").test(trimmed)) {
    return null;
  }

  // For a span the start time drops out and only the end stays.
  const stripped = trimmed.replace(
    new RegExp(
      `^(?:um\\s+)?(?:${variantPattern}|${hourOnly})\\s*(?:Uhr\\s+)?(?=bis\\b|und\\b|[–—-]\\s*\\d)`,
      "i",
    ),
    "",
  ).trim();

  return stripped || null;
}

function parseYMD(s: string): Date {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
}

/** The really due day, for a span the last one. */
export function effectiveDueDate(entry: {
  due_date: string | null;
  end_date?: string | null;
}): string | null {
  return entry.end_date || entry.due_date;
}

/** The end of a span in plain text, with a year only across the year boundary. */
export function formatRangeEnd(
  dueDate: string | null | undefined,
  endDate: string | null | undefined,
  locale: string,
): string | null {
  if (!dueDate || !endDate || endDate === dueDate) return null;
  const tag = locale === "en" ? "en-US" : "de-DE";
  const anderesJahr = endDate.slice(0, 4) !== dueDate.slice(0, 4);
  return new Intl.DateTimeFormat(tag, {
    day: "numeric",
    month: "long",
    ...(anderesJahr ? { year: "numeric" } : {}),
  }).format(parseYMD(endDate));
}

/** 'from' or 'until' before the day number when the source bounded the day. */
export function dateQualifier(entry: {
  type?: string | null;
  end_date?: string | null;
  due_date: string | null;
  is_open_ended?: boolean | null;
}): "from" | "until" | null {
  if (entry.is_open_ended) return "from";
  if (entry.end_date && entry.end_date !== entry.due_date) return null;
  return entry.type === "deadline" ? "until" : null;
}
