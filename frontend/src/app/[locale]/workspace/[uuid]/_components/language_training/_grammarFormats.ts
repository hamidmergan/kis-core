/**
 * Die vier Aufgabenformate der Grammatik-Uebung und was davon gesendet wird.
 *
 * Reine Funktionen, damit sie ohne Browser pruefbar sind. Der Dialog haelt nur den
 * Zustand, die Entscheidungen stehen hier.
 *
 * Die Kuerzel sind dieselben, die das Backend kennt. Sie stehen im Frontend NUR hier,
 * damit ein Tippfehler an einer Stelle auffaellt und nicht an vieren.
 */

export const GRAMMAR_FORMATS = [
  "transform",
  "cloze",
  "statement",
  "choice",
] as const;

export type GrammarFormat = (typeof GRAMMAR_FORMATS)[number];

/**
 * Was an das Backend geht, oder `undefined` fuer gemischt.
 *
 * Gemischt sendet NICHTS. Alle vier anzuhaken ist sachlich gemischt und sendet
 * deshalb ebenfalls nichts. Zwei Schreibweisen fuer denselben Zustand waeren zwei
 * Faelle, die frueher oder spaeter auseinanderlaufen.
 */
export function sentKinds(
  pick: boolean,
  checked: GrammarFormat[],
): string[] | undefined {
  if (!pick) return undefined;
  const gewaehlt = GRAMMAR_FORMATS.filter((f) => checked.includes(f));
  if (gewaehlt.length === 0 || gewaehlt.length === GRAMMAR_FORMATS.length) {
    return undefined;
  }
  return gewaehlt;
}

/** Ob die Formatauswahl den Erstellen-Knopf freigibt. */
export function formatChoiceReady(
  pick: boolean,
  checked: GrammarFormat[],
): boolean {
  return !pick || checked.length > 0;
}

/** Ein Kaestchen umlegen. Die Reihenfolge bleibt die des Katalogs. */
export function toggleFormat(
  checked: GrammarFormat[],
  format: GrammarFormat,
): GrammarFormat[] {
  const drin = checked.includes(format);
  return GRAMMAR_FORMATS.filter((f) =>
    f === format ? !drin : checked.includes(f),
  );
}
