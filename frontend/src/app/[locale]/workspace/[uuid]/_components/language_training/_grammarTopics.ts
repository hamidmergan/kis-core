/**
 * Reine Logik rund um Grammatikthemen.
 *
 * Ein Thema traegt genau ein Musterpaar. Frueher nahm das Formular bis zu drei
 * entgegen, aber der Generator las nie mehr als das erste: er baut daraus die
 * SHAPE TO COPY fuer das Modell und zeigt es dem Lernenden ueber der Aufgabe.
 * Paar zwei und drei wurden gespeichert und von niemandem gelesen, also standen
 * im Formular vier Felder, von denen zwei nichts bewirkten.
 */

export interface ExamplePair {
  before: string;
  after: string;
}

/**
 * Das Paar, das das Formular zeigt: das erste aus der Ausarbeitung, sonst ein
 * leeres. Die Ausarbeitung liefert immer genau eines, ein leeres Paar ist also
 * nur der Notnagel.
 */
export function editedPair(pairs: ExamplePair[]): ExamplePair {
  return pairs[0] ?? { before: "", after: "" };
}

/**
 * Was gespeichert wird: ein Paar zaehlt nur, wenn beide Haelften da sind und
 * sich unterscheiden.
 *
 * Vorher gleich nachher waere kein Muster, sondern ein Satz. Als Vorlage fuer die
 * Generierung wuerde es nichts steuern und dem Lernenden nichts zeigen.
 */
export function usablePairs(pairs: ExamplePair[]): ExamplePair[] {
  return pairs
    .map((p) => ({ before: p.before.trim(), after: p.after.trim() }))
    .filter((p) => p.before && p.after && p.before !== p.after)
    .slice(0, 1);
}

/**
 * Welches Thema nach dem Entfernen ausgewaehlt ist.
 *
 * War ein anderes gewaehlt, bleibt es. War das entfernte gewaehlt, rueckt das
 * nach, das an seine Stelle tritt, beim letzten Eintrag das davor. Ohne diese
 * Nachfolge stuende die Auswahl auf einem Thema, das es nicht mehr gibt, und der
 * Erstellen-Knopf schickte eine Nummer ins Leere.
 */
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

/**
 * Der Namensvorschlag, sofern er etwas anderes sagt als das Getippte.
 *
 * Leer heisst, im Formular steht keine Zeile. Ohne diesen Vergleich stuende bei
 * jedem sauber getippten Thema ein Vorschlag, der nichts sagt, und nach dem dritten
 * Mal liest ihn niemand mehr. Dann waere er auch in dem einen Fall unsichtbar, in
 * dem er zaehlt: "passi", oder ein Name wie "Passiv", der neun Formen gleichzeitig
 * meint und von dem das Modell sich eine aussucht.
 *
 * Verglichen wird ohne Ruecksicht auf Gross und Klein und auf Leerraum. Kein
 * Woerterbuch und keine deutschen Sonderregeln, wie ueberall in diesem Werkzeug.
 */
export function shownSuggestion(typed: string, suggested: string): string {
  const vorschlag = suggested.trim();
  if (!vorschlag) return "";
  const gleichform = (s: string) => s.trim().replace(/\s+/g, " ").toLowerCase();
  return gleichform(typed) === gleichform(vorschlag) ? "" : vorschlag;
}
