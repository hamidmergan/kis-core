/**
 * Die Auswahl in der Vorrats-Karte. Steht getrennt von der Karte, damit sich das
 * Zaehlen pruefen laesst, ohne die Oberflaeche zu starten.
 */

export type PoolCounts = { tools: Record<string, number>; schedule: number };

/** Die fuenf Werkzeuge mit Vorrat, in derselben Reihenfolge wie in der Karte. */
export const POOL_TOOLS = [
  "flashcards", "karteikarten", "quiz", "grammatik", "wortschatz",
] as const;

/** Wie viel die aktuelle Auswahl wegwirft. Steht in der Sicherheitsabfrage. */
export function chosenCount(
  counts: PoolCounts, tools: string[], schedule: boolean,
): number {
  const aufgaben = tools.reduce((summe, tool) => summe + (counts.tools[tool] ?? 0), 0);
  return aufgaben + (schedule ? counts.schedule : 0);
}
