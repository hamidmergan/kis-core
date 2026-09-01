/** A topic carries up to MAX_EXAMPLES pattern pairs, one per musterweg. */

export interface ExamplePair {
  before: string;
  after: string;
}

// Mirrors backend/src/features/ai_assistant/repository/grammar_topics.py.
export const MAX_EXAMPLES = 3;

/** The pairs the form shows, at least one empty row. */
export function editedPairs(pairs: ExamplePair[]): ExamplePair[] {
  return pairs.length > 0 ? pairs : [{ before: "", after: "" }];
}

/** A pair only counts when both halves are there and differ. */
export function usablePairs(pairs: ExamplePair[]): ExamplePair[] {
  return pairs
    .map((p) => ({ before: p.before.trim(), after: p.after.trim() }))
    .filter((p) => p.before && p.after && p.before !== p.after)
    .slice(0, MAX_EXAMPLES);
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
