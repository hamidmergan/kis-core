export const URGENCY_RED = "#B91C1C";
export const URGENCY_ORANGE = "#EA580C";

export function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/**
 * Foreground color for a deadline's date/time text:
 *   today → red, less than 7 days away → orange, else null (use default).
 * Past deadlines fall through to default since the "vor X Tagen" label
 * already conveys overdue status.
 */
export function urgencyColor(dueDate: string | null | undefined, today: string): string | null {
  if (!dueDate) return null;
  if (dueDate < today) return null;
  if (dueDate === today) return URGENCY_RED;
  const days = Math.round(
    (new Date(dueDate).getTime() - new Date(today).getTime()) / 86_400_000,
  );
  if (days > 0 && days < 7) return URGENCY_ORANGE;
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
export function cleanScheduleDescription(
  description: string | null | undefined,
  dueTime: string | null | undefined,
): string | null {
  if (!description) return null;
  const trimmed = description.trim();
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
