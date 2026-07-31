/** Der Prozentwert im Ring auf einer Uebungskarte.
 *
 * Gezaehlt wird im Backend: der Anteil der Karten, deren LETZTE Antwort richtig
 * war. Hier wird der fertige Wert nur noch abgesichert. Vorher rechnete die
 * Oberflaeche selbst und teilte dabei die richtigen Antworten EINES Durchgangs
 * durch alle Karten des Satzes. Wurde eine Uebung unterbrochen, begann fuer den
 * Browser mittendrin ein neuer Durchgang, und der Ring zeigte weniger, als der
 * Lernende richtig hatte (gemeldet: 40 Prozent bei 4 von 5 richtig).
 */

export function setProgressPct(set: { progress_pct?: number }): number {
  const pct = set.progress_pct;
  if (typeof pct !== "number" || Number.isNaN(pct)) return 0;
  return Math.min(100, Math.max(0, Math.round(pct)));
}
