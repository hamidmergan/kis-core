/**
 * Reine Logik rund um Grammatikthemen.
 *
 * Ein Thema traegt bis zu drei Musterpaare. Alle steuern das Modell, aber die
 * Aufgabe zeigt dem Lernenden genau eines, und das ist das erste. Deshalb ist die
 * Reihenfolge in der Liste keine Nebensache.
 */

export const MAX_EXAMPLES = 3;

export interface ExamplePair {
  before: string;
  after: string;
}

/**
 * Die Zeilen, die das Formular anzeigt: die vorhandenen Paare plus eine leere zum
 * Ausfuellen, gedeckelt bei MAX_EXAMPLES.
 *
 * Ohne die leere Zeile braeuchte es einen Knopf "Beispiel hinzufuegen", und der
 * waere ein Klick mehr fuer etwas, das ohnehin fast jeder tut.
 */
export function exampleSlots(pairs: ExamplePair[]): ExamplePair[] {
  if (pairs.length >= MAX_EXAMPLES) return pairs.slice(0, MAX_EXAMPLES);
  return [...pairs, { before: "", after: "" }];
}

/**
 * Was gespeichert wird: leere Zeilen fallen raus, und ein Paar zaehlt nur, wenn
 * beide Haelften da sind und sich unterscheiden.
 *
 * Vorher gleich nachher waere kein Muster, sondern ein Satz. Als Vorlage fuer die
 * Generierung wuerde es nichts steuern und dem Lernenden nichts zeigen.
 */
export function usablePairs(pairs: ExamplePair[]): ExamplePair[] {
  return pairs
    .map((p) => ({ before: p.before.trim(), after: p.after.trim() }))
    .filter((p) => p.before && p.after && p.before !== p.after)
    .slice(0, MAX_EXAMPLES);
}
