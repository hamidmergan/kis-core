/** Heute ist kein Fehler, darum das Akzentblau und dieselbe Farbe wie die Heute-Zelle im Raster. */
export const URGENCY_TODAY = "var(--kb-dark)";
export const URGENCY_SOON = "var(--warn)";

export function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/**
 * Foreground color for a deadline's date/time text:
 *   today → accent blue, less than 7 days away → orange, else null (use default).
 * Past deadlines fall through to default since the "vor X Tagen" label
 * already conveys overdue status.
 */
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

/**
 * Strip start-time repetition from a schedule entry's description.
 *
 * The classifier sometimes leaks the due_time back into `description` (e.g.
 * description="2359 Uhr" while due_time="23:59", or description="10 bis 13:15
 * Uhr" while due_time="10:00"). The UI shows due_time separately, so the
 * leading repetition is pure noise. For ranges the trailing "bis HH:MM Uhr"
 * is kept because it carries the end-time, which the data model has no slot
 * for.
 */
/**
 * Wirft ein "bis <Datum>" oder "ab <Datum>" aus der Beschreibung, wenn dort der EIGENE
 * Tag des Eintrags steht.
 *
 * Das stammt aus Laeufen, bevor es die Spalte fuer das Ende gab: die Extraktion schrieb
 * das zweite Datum der Zeile als Text in die Beschreibung, und der Eintrag am Ende der
 * Spanne trug dann seinen eigenen Tag nochmal unter sich ("27 SEP - Belegung der Module -
 * bis 27.09.2026"). Zeigt der Text auf einen ANDEREN Tag, bleibt er stehen, dort steckt
 * noch echte Information.
 */
function stripSelfDate(text: string, dueDate: string | null | undefined): string {
  if (!dueDate || !/^\d{4}-\d{2}-\d{2}$/.test(dueDate)) return text;
  const [jahr, monat, tag] = dueDate.split("-");
  const t = String(Number(tag));
  const m = String(Number(monat));
  // "27.09.2026", "27.9.2026", "27.09.26" und dieselben Formen ohne fuehrende Null.
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

  // 2) Range like "10 bis 13:15 Uhr" / "10:00–13:15": strip the leading start-time
  //    so only the end remains.
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

/**
 * Der Tag, an dem der Termin wirklich faellig ist: bei einer Spanne der letzte.
 *
 * Danach richtet sich, ab wann die Ansicht warnt und wann sie abblendet. Eine
 * Betreuungszeit vom 28.09. bis zum 21.01. laeuft vier Monate, sie ist am 29.09. weder
 * vorbei noch dringend.
 */
export function effectiveDueDate(entry: {
  due_date: string | null;
  end_date?: string | null;
}): string | null {
  return entry.end_date || entry.due_date;
}

/**
 * Das Ende einer Zeitspanne im Klartext: "2. November", "21. Januar 2027".
 *
 * Das Jahr steht nur dort, wo die Spanne den Jahreswechsel ueberschreitet. Ohne diese
 * Regel waere "bis 21. Januar" bei einer Spanne ab dem 28. September mehrdeutig, der
 * Leser haette keinen Anhalt, welcher Januar gemeint ist.
 *
 * Gibt null zurueck, wenn es keine Spanne ist.
 */
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

/**
 * "ab" oder "bis" vor der Tagesnummer, wenn die Quelle den Tag so eingegrenzt hat.
 *
 * Die Quelle schreibt "ab 15.09.2026 Freischaltung der Module" und "bis 03.01.2027
 * Eingabe der Pruefungsvorleistungen". Ohne den Marker sieht beides aus wie ein Termin AN
 * diesem Tag. Er steht an der Plakette und nicht als Zeile in der Karte, damit das Datum
 * nicht ein zweites Mal dasteht.
 *
 * Eine Spanne braucht ihn nicht, dort sagt die Zeile "bis <Datum>" schon alles.
 */
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
