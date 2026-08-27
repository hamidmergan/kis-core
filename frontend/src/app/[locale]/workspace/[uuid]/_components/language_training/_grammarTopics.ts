/** A topic carries exactly one pattern pair, the generator never read more. */

export interface ExamplePair {
  before: string;
  after: string;
}

/** The pair the form shows, otherwise an empty one. */
export function editedPair(pairs: ExamplePair[]): ExamplePair {
  return pairs[0] ?? { before: "", after: "" };
}

/** A pair only counts when both halves are there and differ. */
export function usablePairs(pairs: ExamplePair[]): ExamplePair[] {
  return pairs
    .map((p) => ({ before: p.before.trim(), after: p.after.trim() }))
    .filter((p) => p.before && p.after && p.before !== p.after)
    .slice(0, 1);
}

/** Which topic is selected after the removal. */
export function nextTopicId(
  topics: { id: number }[],
  removedId: number,
  currentId: number | null,
): number | null {
  if (currentId !== null && currentId !== removedId) return currentId;
  const rest = topics.filter((t) => t.id !== removedId);
  if (!rest.length) return null;
  if (currentId === null) return rest[0].id;
  const stelle = topics.findIndex((t) => t.id === removedId);
  return rest[Math.min(Math.max(stelle, 0), rest.length - 1)].id;
}

/** The name suggestion, only when it says something other than what was typed. */
export function shownSuggestion(typed: string, suggested: string): string {
  const vorschlag = suggested.trim();
  if (!vorschlag) return "";
  const gleichform = (s: string) => s.trim().replace(/\s+/g, " ").toLowerCase();
  return gleichform(typed) === gleichform(vorschlag) ? "" : vorschlag;
}
