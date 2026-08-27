/** The selection of the pool card, kept separate so it stays testable. */

export type PoolCounts = { tools: Record<string, number>; schedule: number };

/** The five tools with a pool, in the same order as in the card. */
export const POOL_TOOLS = [
  "flashcards", "karteikarten", "quiz", "grammatik", "wortschatz",
] as const;

/** How much the current selection throws away, shown in the confirmation. */
export function chosenCount(
  counts: PoolCounts, tools: string[], schedule: boolean,
): number {
  const aufgaben = tools.reduce((summe, tool) => summe + (counts.tools[tool] ?? 0), 0);
  return aufgaben + (schedule ? counts.schedule : 0);
}
