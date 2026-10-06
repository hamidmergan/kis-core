type ShowIf = { question_id: string; in: string[] };
type Wert = string | string[];

/** Whether a question's prerequisite answer allows it to appear at all. */
export function istSichtbar(
  frage: { show_if?: ShowIf },
  antworten: Record<string, Wert>,
): boolean {
  if (!frage.show_if) return true;
  const wert = antworten[frage.show_if.question_id];
  if (wert === undefined) return false;
  if (Array.isArray(wert)) return frage.show_if.in.some((w) => wert.includes(w));
  return frage.show_if.in.includes(String(wert));
}

/** The next index in the given direction whose question is actually visible, clamped to the list's bounds. */
export function naechsterSichtbarerIndex(
  fragen: { show_if?: ShowIf }[],
  antworten: Record<string, Wert>,
  von: number,
  richtung: 1 | -1,
): number {
  let i = von;
  while (i >= 0 && i < fragen.length && !istSichtbar(fragen[i], antworten)) i += richtung;
  return i;
}
