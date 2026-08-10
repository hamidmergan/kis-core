/** Der Vergleich einer eingetippten Lücke mit ihrer Lösung.
 *
 * Er läuft im Browser und nicht im Backend. Die Lösungen kommen beim Laden des
 * Sets mit, das ist Absicht: der Lückentext ist eine Übung und keine Prüfung, und
 * wer schummeln will, fragt ohnehin ein Modell.
 *
 * Gemessen wird über ZEICHEN und nicht über Wörter. `overlap_ratio` im Backend
 * zählt ganze Wörter und liefert bei einer Ein-Wort-Antwort nur 0 oder 1, damit
 * liesse sich ein Tippfehler nicht von einem falschen Wort unterscheiden.
 */

export type ClozeVerdict = "correct" | "close" | "wrong";

// Ab dieser Zeichenähnlichkeit gilt eine Antwort als fast richtig. Derselbe Wert
// wie _CLOSE_RATIO in aia_grammar_check.py, damit ein Lernender im Lückentext
// nicht anders beurteilt wird als in der Grammatik-Übung.
const CLOSE_RATIO = 0.72;

const PARENS_RE = /\([^)]*\)/g;
const PUNCT_RE = /\p{P}/gu;
const WS_RE = /\s+/g;

export function normalizeAnswer(text: string): string {
  if (!text) return "";
  return text
    .replace(PARENS_RE, " ")
    .replace(PUNCT_RE, "")
    .replace(WS_RE, " ")
    .trim()
    .toLowerCase();
}

/** Levenshtein-Abstand, zwei Zeilen statt der ganzen Matrix. */
function distance(a: string, b: string): number {
  if (a === b) return 0;
  if (!a.length) return b.length;
  if (!b.length) return a.length;
  let prev = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    for (let j = 1; j <= b.length; j++) {
      cur[j] = Math.min(
        prev[j] + 1,
        cur[j - 1] + 1,
        prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1),
      );
    }
    prev = cur;
  }
  return prev[b.length];
}

export function checkGap(given: string, expected: string): ClozeVerdict {
  const a = normalizeAnswer(given);
  const b = normalizeAnswer(expected);
  if (!a || !b) return "wrong";
  if (a === b) return "correct";
  const ratio = 1 - distance(a, b) / Math.max(a.length, b.length);
  return ratio >= CLOSE_RATIO ? "close" : "wrong";
}
