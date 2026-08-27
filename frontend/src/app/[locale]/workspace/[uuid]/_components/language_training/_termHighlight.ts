/** Splits an example sentence into pieces and marks the learned word in it. */

export type ExampleSegment = { text: string; focus: boolean };

// Words that can stand before the actual form and mark nothing themselves.
const LEADING_RE = /^(?:der|die|das|den|dem|des|ein|eine|einen|einem|einer|eines|ich|du|er|sie|es|wir|ihr|man|hat|habe|hast|haben|ist|bin|bist|sind|war|waren|sich|zu)\b\s*/i;

// Endings an inflected form appends to the base form.
const ENDINGS = "(?:innen|ern|ses|sen|se|en|em|er|es|in|e|n|s)?";

const LETTER_RE = /[\p{L}\p{N}]/u;
const EDGE_RE = /^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu;

// Anything shorter is not marked, otherwise a two-letter word colours half the sentence.
const MIN_LENGTH = 3;

function escapeRe(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Strips articles, pronouns and bracketed additions off a word form. */
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
    // The longest form first so the assembly does not stick on the short partial word.
    .sort((a, b) => b.length - a.length);
  if (!sentence || needles.length === 0) return [{ text: sentence, focus: false }];

  const pattern = new RegExp(`(?:${needles.map(escapeRe).join("|")})${ENDINGS}`, "giu");
  const segments: ExampleSegment[] = [];
  let cursor = 0;
  for (const hit of sentence.matchAll(pattern)) {
    const start = hit.index ?? 0;
    const end = start + hit[0].length;
    // Only a whole word goes bold, never a piece of a longer word.
    if (LETTER_RE.test(sentence[start - 1] || "") || LETTER_RE.test(sentence[end] || "")) continue;
    if (start > cursor) segments.push({ text: sentence.slice(cursor, start), focus: false });
    segments.push({ text: hit[0], focus: true });
    cursor = end;
  }
  if (cursor < sentence.length) segments.push({ text: sentence.slice(cursor), focus: false });
  return segments;
}
