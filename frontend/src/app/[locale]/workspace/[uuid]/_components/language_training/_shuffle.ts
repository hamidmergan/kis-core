/** Mischen der Antwortoptionen einer Aufgabe.
 *
 * Gemischt wird, damit die richtige Antwort nicht immer an derselben Stelle steht.
 * Ausgenommen sind Aufgaben mit zwei Optionen: das ist Richtig/Falsch, und dort ist
 * die Reihenfolge Teil der Beschriftung. "Falsch, Richtig" liest sich wie ein Fehler.
 */

type WithOptions = { options?: string[]; correct_idx?: number };

export function shuffleOptions<T extends WithOptions>(item: T): T {
  const options = item.options;
  if (!options || item.correct_idx === undefined || options.length < 3) return item;
  const indices = options.map((_, i) => i);
  for (let i = indices.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [indices[i], indices[j]] = [indices[j], indices[i]];
  }
  return {
    ...item,
    options: indices.map((i) => options[i]),
    correct_idx: indices.indexOf(item.correct_idx),
  };
}
