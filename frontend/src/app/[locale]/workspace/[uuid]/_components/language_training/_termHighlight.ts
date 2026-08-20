/** Zerlegt einen Beispielsatz in Stuecke und markiert darin das gelernte Wort. */

export type ExampleSegment = { text: string; focus: boolean };

// Woerter, die vor der eigentlichen Form stehen koennen und selbst nichts markieren.
const LEADING_RE = /^(?:der|die|das|den|dem|des|ein|eine|einen|einem|einer|eines|ich|du|er|sie|es|wir|ihr|man|hat|habe|hast|haben|ist|bin|bist|sind|war|waren|sich|zu)\b\s*/i;

// Endungen, die eine gebeugte Form an die Grundform haengt.
const ENDINGS = "(?:innen|ern|ses|sen|se|en|em|er|es|in|e|n|s)?";

const LETTER_RE = /[\p{L}\p{N}]/u;
const EDGE_RE = /^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu;

// Kuerzeres wird nicht markiert, sonst faerbt ein "es" den halben Satz ein.
const MIN_LENGTH = 3;

function escapeRe(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Schaelt Artikel, Pronomen und Klammerzusaetze von einer Wortform ab. */
function bareForm(form: string): string {
  let out = form.replace(/\([^)]*\)/g, " ").replace(/\s+/g, " ").trim();
  let previous = "";
  while (out !== previous) {
    previous = out;
    out = out.replace(LEADING_RE, "");
  }
  return out.replace(EDGE_RE, "");
}

export function splitExample(sentence: string, forms: (string | undefined | null)[]): ExampleSegment[] {
  const needles = Array.from(new Set(forms.map(f => bareForm(f || "")).filter(f => f.length >= MIN_LENGTH)))
    // Die laengste Form zuerst, damit der Zusammenbau nicht am kurzen Teilwort haengen bleibt.
    .sort((a, b) => b.length - a.length);
  if (!sentence || needles.length === 0) return [{ text: sentence, focus: false }];

  const pattern = new RegExp(`(?:${needles.map(escapeRe).join("|")})${ENDINGS}`, "giu");
  const segments: ExampleSegment[] = [];
  let cursor = 0;
  for (const hit of sentence.matchAll(pattern)) {
    const start = hit.index ?? 0;
    const end = start + hit[0].length;
    // Nur ein ganzes Wort wird fett, nie ein Stueck aus einem laengeren Wort.
    if (LETTER_RE.test(sentence[start - 1] || "") || LETTER_RE.test(sentence[end] || "")) continue;
    if (start > cursor) segments.push({ text: sentence.slice(cursor, start), focus: false });
    segments.push({ text: hit[0], focus: true });
    cursor = end;
  }
  if (cursor < sentence.length) segments.push({ text: sentence.slice(cursor), focus: false });
  return segments;
}
