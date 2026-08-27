/** The comparison of a typed gap, in the browser and over characters instead of words. */

export type ClozeVerdict = "correct" | "close" | "wrong";

// From this similarity on an answer counts as close, as in the backend.
const CLOSE_RATIO = 0.72;

const PARENS_RE = /\([^)]*\)/g;
const PUNCT_RE = /\p{P}/gu;
const WS_RE = /\s+/g;

// Folds the sharp s like the backend, JavaScript does not know this folding.
const SHARP_S_RE = /ß/g;

export function normalizeAnswer(text: string): string {
  if (!text) return "";
  return text
    .replace(PARENS_RE, " ")
    .replace(PUNCT_RE, " ")
    .replace(WS_RE, " ")
    .trim()
    .toLowerCase()
    .replace(SHARP_S_RE, "ss");
}

/** Levenshtein distance, two rows instead of the whole matrix. */
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
