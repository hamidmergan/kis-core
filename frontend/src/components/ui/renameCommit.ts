/**
 * Was beim Umbenennen mit einer Eingabe geschehen soll.
 *
 * Eigene Datei neben der Komponente, wie ``backdropClose`` daneben: die
 * Entscheidung ist pruefbare Logik, das Feld drumherum ist nur Darstellung.
 * Hier stehen die drei Faelle, die man beim Umbenennen leicht verwechselt.
 */

export type RenameAction =
  /** Nichts zu tun, Feld einfach schliessen. Kein Fehler, sondern ein Abbruch. */
  | { kind: "abort" }
  /** Speichern mit genau diesem Namen. */
  | { kind: "save"; title: string };

/**
 * Leer oder unveraendert heisst abbrechen, sonst speichern.
 *
 * Leer loescht bewusst keinen Namen: ein Ergebnis ohne Namen waere in der Liste
 * nicht mehr auffindbar. Unveraendert spart den Aufruf, sonst schriebe jedes
 * Verlassen des Feldes denselben Namen erneut in die Datenbank.
 */
export function renameCommit(entwurf: string, aktuell: string): RenameAction {
  const naechster = entwurf.trim();
  if (!naechster || naechster === aktuell.trim()) return { kind: "abort" };
  return { kind: "save", title: naechster };
}

/**
 * Die Meldung, die im Feld stehen bleibt, wenn das Speichern abgelehnt wurde.
 *
 * Der Grund vom Server hat Vorrang, denn er sagt, WAS nicht ging. Nur wenn keiner
 * ankommt, steht der allgemeine Satz da.
 */
export function renameErrorText(fehler: unknown, allgemein: string): string {
  if (fehler instanceof Error && fehler.message) return fehler.message;
  return allgemein;
}
