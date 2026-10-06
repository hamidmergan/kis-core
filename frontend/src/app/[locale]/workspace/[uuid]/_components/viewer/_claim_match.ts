// Finds the spot on a PDF page that a chip's claim rests on, pure and testable.

export interface Span {
  start: number;
  /** Exclusive end. */
  end: number;
}

export interface ClaimMatch {
  /** A sentence or paragraph, or only the strongest words when none stands out. */
  kind: "passage" | "keywords";
  spans: Span[];
}

/** Whitespace runs collapse to one space, runs with a line break to one newline. */
export function normalizePageText(raw: string): { text: string; toRaw: number[] } {
  const toRaw: number[] = [];
  let text = "";
  let runStart = -1;
  let runHasBreak = false;
  const flush = () => {
    if (runStart < 0) return;
    text += runHasBreak ? "\n" : " ";
    toRaw.push(runStart);
    runStart = -1;
    runHasBreak = false;
  };
  for (let i = 0; i < raw.length; i++) {
    const ch = raw[i];
    if (ch === " " || ch === "\t" || ch === "\r" || ch === "\n" || ch === " ") {
      if (runStart < 0) runStart = i;
      if (ch === "\r" || ch === "\n") runHasBreak = true;
      continue;
    }
    flush();
    text += ch;
    toRaw.push(i);
  }
  flush();
  return { text, toRaw };
}


// --- Tokens and numbers ---------------------------------------------------------------

interface Token {
  norm: string;
  start: number;
  end: number;
  /** Set when the token is a number, written in digits or in words. */
  value?: number;
}

export interface NumberHit {
  value: number;
  start: number;
  end: number;
}

const TOKEN_RE = /\p{N}+(?:[.,]\p{N}+)*|\p{L}+/gu;

/** Lower case without accents, so a broken text layer still matches. */
function normWord(s: string): string {
  return s.normalize("NFKD").replace(/\p{M}+/gu, "").toLowerCase();
}

/** "25.000" is a thousand group, "25,5" and "3.14" are decimals. */
function parseDigits(s: string): number {
  const parts = s.split(/[.,]/);
  if (parts.length === 1) return Number(s);
  const seps = s.match(/[.,]/g) ?? [];
  const sameSep = seps.every((c) => c === seps[0]);
  const allThree = parts.slice(1).every((p) => p.length === 3);
  if (sameSep && allThree) return Number(parts.join(""));
  return Number(parts.slice(0, -1).join("") + "." + parts[parts.length - 1]);
}

const MULTIPLIERS: Record<string, number> = {
  k: 1e3, tsd: 1e3, tausend: 1e3, thousand: 1e3,
  mio: 1e6, million: 1e6, millionen: 1e6,
  mrd: 1e9, milliarde: 1e9, milliarden: 1e9, billion: 1e9, bn: 1e9,
};

const DE_ATOMS: Record<string, number> = {
  null: 0, zwei: 2, drei: 3, vier: 4, funf: 5, fuenf: 5, sechs: 6, sieben: 7, acht: 8, neun: 9,
  zehn: 10, elf: 11, zwolf: 12, zwoelf: 12, dreizehn: 13, vierzehn: 14, funfzehn: 15, fuenfzehn: 15,
  sechzehn: 16, siebzehn: 17, achtzehn: 18, neunzehn: 19,
  zwanzig: 20, dreissig: 30, dreißig: 30, vierzig: 40, funfzig: 50, fuenfzig: 50,
  sechzig: 60, siebzig: 70, achtzig: 80, neunzig: 90,
};
// "ein" counts only inside a compound, alone it is an article.
const DE_ONE = new Set(["ein", "eins", "eine"]);

/** A German number word such as "fünfundzwanzigtausend", null when it is no number. */
function parseGermanWord(w: string): number | null {
  const rec = (s: string): number | null => {
    if (s === "") return 0;
    if (s.startsWith("und")) s = s.slice(3);
    for (const [word, mult] of [["tausend", 1000], ["hundert", 100]] as const) {
      const i = s.indexOf(word);
      if (i < 0) continue;
      const left = s.slice(0, i);
      const l = left === "" ? 1 : rec(left);
      const r = rec(s.slice(i + word.length));
      if (l == null || r == null || l === 0) return null;
      return l * mult + r;
    }
    const u = s.indexOf("und");
    if (u > 0) {
      const unit = s.slice(0, u);
      const tens = s.slice(u + 3);
      const uv = DE_ONE.has(unit) ? 1 : DE_ATOMS[unit];
      const tv = DE_ATOMS[tens];
      if (uv != null && uv < 10 && tv != null && tv >= 20 && tv < 100) return uv + tv;
      return null;
    }
    if (DE_ONE.has(s)) return 1;
    return DE_ATOMS[s] ?? null;
  };
  if (w.length < 4 || DE_ONE.has(w)) return null;
  const v = rec(w);
  return v == null ? null : v;
}

const EN_ATOMS: Record<string, number> = {
  zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9,
  ten: 10, eleven: 11, twelve: 12, thirteen: 13, fourteen: 14, fifteen: 15, sixteen: 16,
  seventeen: 17, eighteen: 18, nineteen: 19, twenty: 20, thirty: 30, forty: 40, fifty: 50,
  sixty: 60, seventy: 70, eighty: 80, ninety: 90,
};
const EN_SCALES: Record<string, number> = { hundred: 100, thousand: 1e3, million: 1e6, billion: 1e9 };

/** Raw tokens with a value on every number, digits and words alike. */
function tokenize(text: string): Token[] {
  const toks: Token[] = [];
  for (const m of text.matchAll(TOKEN_RE)) {
    const start = m.index ?? 0;
    const raw = m[0];
    const tok: Token = { norm: normWord(raw), start, end: start + raw.length };
    if (/^\p{N}/u.test(raw)) tok.value = parseDigits(raw);
    else {
      const de = parseGermanWord(tok.norm);
      if (de != null) tok.value = de;
    }
    toks.push(tok);
  }
  return joinHyphenated(text, toks);
}

/** "Ver-" at a line end and "waltung" on the next become one token. */
function joinHyphenated(text: string, toks: Token[]): Token[] {
  const out: Token[] = [];
  for (const tok of toks) {
    const prev = out[out.length - 1];
    if (prev && prev.value == null && tok.value == null && /^-\s+$/.test(text.slice(prev.end, tok.start))) {
      prev.norm += tok.norm;
      prev.end = tok.end;
      continue;
    }
    out.push({ ...tok });
  }
  return out;
}

/** Only a space or nothing may sit between two tokens for them to belong together. */
function adjacent(text: string, a: Token, b: Token): boolean {
  return /^[\s.\-]{0,2}$/.test(text.slice(a.end, b.start));
}

/** Runs of English number words and multiplier suffixes fold into one number. */
function foldNumbers(text: string, toks: Token[]): Token[] {
  const out: Token[] = [];
  let i = 0;
  while (i < toks.length) {
    const t = toks[i];
    // An English run: "two hundred and fifty", "twenty-five thousand".
    if (t.value == null && EN_ATOMS[t.norm] != null) {
      let total = 0, current = 0, j = i, last = t;
      let used = 0;
      while (j < toks.length && (j === i || adjacent(text, toks[j - 1], toks[j]))) {
        const w = toks[j].norm;
        if (EN_ATOMS[w] != null) { current += EN_ATOMS[w]; used++; }
        else if (w === "hundred") { current = (current || 1) * 100; used++; }
        else if (EN_SCALES[w] != null) { total += (current || 1) * EN_SCALES[w]; current = 0; used++; }
        else if (w === "and" && used > 0) { /* filler */ }
        else break;
        last = toks[j];
        j++;
      }
      // A trailing "and" is not part of the number.
      while (j > i && toks[j - 1].norm === "and") { j--; last = toks[j - 1]; }
      out.push({ norm: text.slice(t.start, last.end), start: t.start, end: last.end, value: total + current });
      i = j;
      continue;
    }
    if (t.value != null) {
      const next = toks[i + 1];
      const mult = next && adjacent(text, t, next) ? MULTIPLIERS[next.norm] : undefined;
      if (mult != null) {
        out.push({ norm: text.slice(t.start, next.end), start: t.start, end: next.end, value: t.value * mult });
        i += 2;
        continue;
      }
    }
    out.push(t);
    i++;
  }
  return out;
}

function tokens(text: string): Token[] {
  return foldNumbers(text, tokenize(text));
}

/** Every number in the text with its position, however it is written. */
export function extractNumbers(text: string): NumberHit[] {
  return tokens(text).filter((t) => t.value != null).map((t) => ({ value: t.value as number, start: t.start, end: t.end }));
}


// --- Units of the page ----------------------------------------------------------------

const SENTENCE_END = /[.!?…。！？؟।]["'”’»)\]]*$/u;
// A sentence end inside a line, followed by a space.
const SENTENCE_BREAK = /[.!?…。！？؟।]["'”’»)\]]*(?=\s)/gu;
const UNIT_MAX_CHARS = 600;
// A line this much shorter than the others ends a paragraph or is a heading.
const SHORT_LINE_SHARE = 0.6;
// A bullet or a numbering opens a new unit on a slide.
const BULLET_START = /^\s*(?:[•●○◦▪▫‣►▸■□➢➤✓✔→\-–—*]|\d{1,2}[.)])\s/u;
// A line without lower case letters is a heading and stands alone.
const HEADING_LINE = /^[^\p{Ll}]*\p{Lu}[^\p{Ll}]*$/u;

/** Sentences of prose and lines of a slide, as spans of the normalised text. */
export function segmentUnits(text: string): Span[] {
  const lines: Span[] = [];
  let pos = 0;
  for (const line of text.split("\n")) {
    if (line.trim()) lines.push({ start: pos, end: pos + line.length });
    pos += line.length + 1;
  }
  const lens = lines.map((l) => l.end - l.start).filter((n) => n >= 20).sort((a, b) => a - b);
  const median = lens.length ? lens[Math.floor(lens.length / 2)] : 0;

  const units: Span[] = [];
  let open: Span | null = null;
  const close = () => { if (open) units.push(open); open = null; };
  for (const line of lines) {
    const body = text.slice(line.start, line.end);
    const standsAlone = BULLET_START.test(body) || HEADING_LINE.test(body);
    if (standsAlone) close();
    // Sentence ends inside the line split it into fragments.
    const frags: Span[] = [];
    let last = line.start;
    for (const m of body.matchAll(SENTENCE_BREAK)) {
      const cut = line.start + (m.index ?? 0) + m[0].length;
      const before = body.slice(Math.max(0, (m.index ?? 0) - 2), m.index ?? 0);
      // "z. B." and initials do not end a sentence.
      if (/(^|\s)\p{L}$/u.test(before)) continue;
      frags.push({ start: last, end: cut });
      last = cut;
    }
    if (last < line.end) frags.push({ start: last, end: line.end });
    for (const frag of frags) {
      const fragText = text.slice(frag.start, frag.end).trim();
      if (!fragText) continue;
      const s = frag.start + (frag.end - frag.start - text.slice(frag.start, frag.end).trimStart().length);
      const e = s + fragText.length;
      if (open && open.end - open.start + (e - open.start) <= UNIT_MAX_CHARS * 2 && e - open.start <= UNIT_MAX_CHARS) open.end = e;
      else { close(); open = { start: s, end: e }; }
      if (SENTENCE_END.test(fragText)) close();
    }
    // A short line without a sentence end is a heading or a paragraph end.
    const lineLen = line.end - line.start;
    if (open && (HEADING_LINE.test(body) || (median > 0 && lineLen < median * SHORT_LINE_SHARE))) close();
  }
  close();
  return units;
}


// --- Matching --------------------------------------------------------------------------

interface Term {
  key: string;
  weight: number;
  strong: boolean;
  value?: number;
  /** Set when the word also stands in the file name. */
  fromTitle?: boolean;
}

const MIN_WORD_LEN = 3;
// Shorter words are mostly function words and only break ties.
const MEANINGFUL_WORD_LEN = 5;
const STRONG_WORD_LEN = 9;
const STRONG_NUMBER = 10;
// A term in more than this share of the units says nothing about the spot.
const COMMON_SHARE = 0.4;
const MIN_UNITS_FOR_DF = 5;
const MAX_KEYWORDS = 8;
const PASSAGE_MAX_CHARS = 700;
const GROW_STEPS = 6;
// A prefix stands in for an inflection ending, a longer rest makes it another word.
const MAX_ENDING_CHARS = 3;
// Function words only decide between units that score the same otherwise.
const TIE_WEIGHT = 0.01;

/** Words of the file name repeat in headers and footers, so they carry little. */
function titleWords(title: string | undefined): Set<string> {
  const words = new Set<string>();
  for (const t of tokens(title ?? "")) if (t.value == null && t.norm.length >= MIN_WORD_LEN) words.add(t.norm);
  return words;
}

function claimTerms(claim: string, title?: string): Term[] {
  const seen = new Set<string>();
  const out: Term[] = [];
  const weak = titleWords(title);
  for (const t of tokens(claim)) {
    if (t.value != null) {
      const key = `#${t.value}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const strong = Math.abs(t.value) >= STRONG_NUMBER;
      out.push({ key, weight: strong ? 2 : 1, strong, value: t.value });
      continue;
    }
    if (t.norm.length < MIN_WORD_LEN || seen.has(t.norm)) continue;
    seen.add(t.norm);
    if ([...weak].some((w) => wordMatches(w, t.norm))) {
      out.push({ key: t.norm, weight: 0.5, strong: false, fromTitle: true });
      continue;
    }
    const strong = t.norm.length >= STRONG_WORD_LEN;
    const weight = strong ? 1.5 : t.norm.length >= MEANINGFUL_WORD_LEN ? 1 : 0.5;
    out.push({ key: t.norm, weight, strong });
  }
  return out;
}

/** Only a number or a word of some length may decide where the passage lies. */
function meaningful(term: Term): boolean {
  return !term.fromTitle && (term.value != null || term.key.length >= MEANINGFUL_WORD_LEN);
}

/** Equal, or one the prefix of the other, which stands in for a stemmer. */
function wordMatches(a: string, b: string): boolean {
  if (a === b) return true;
  if (a.length < 5 || b.length < 5 || Math.abs(a.length - b.length) > MAX_ENDING_CHARS) return false;
  return a.startsWith(b) || b.startsWith(a);
}

function termHits(term: Term, toks: Token[]): Token[] {
  if (term.value != null) return toks.filter((t) => t.value != null && t.value === term.value);
  return toks.filter((t) => t.value == null && wordMatches(t.norm, term.key));
}

/** The passage the claim rests on, or its strongest words, or null. */
export function findClaimSpot(pageText: string, claim: string, title?: string): ClaimMatch | null {
  if (!pageText.trim() || !claim.trim()) return null;
  const terms = claimTerms(claim, title);
  if (!terms.length) return null;
  const units = segmentUnits(pageText);
  if (!units.length) return null;
  const unitToks = units.map((u) => tokens(pageText.slice(u.start, u.end)).map((t) => ({ ...t, start: t.start + u.start, end: t.end + u.start })));
  // A heading never joins a passage, it only names the slide.
  const isHeading = units.map((u) => HEADING_LINE.test(pageText.slice(u.start, u.end)));

  // Which terms each unit carries, common ones dropped.
  const hitsPerUnit: Set<string>[] = units.map(() => new Set());
  const df = new Map<string, number>();
  for (const term of terms) {
    unitToks.forEach((toks, i) => {
      if (termHits(term, toks).length) {
        hitsPerUnit[i].add(term.key);
        df.set(term.key, (df.get(term.key) ?? 0) + 1);
      }
    });
  }
  const live = terms.filter((t) => units.length < MIN_UNITS_FOR_DF || (df.get(t.key) ?? 0) <= units.length * COMMON_SHARE);
  // A term found in several units points less to one of them.
  const weightOf = (keys: Set<string>) => live.reduce((sum, t) => {
    if (!keys.has(t.key)) return sum;
    return sum + (meaningful(t) ? t.weight / (df.get(t.key) ?? 1) : TIE_WEIGHT);
  }, 0);
  const scores = hitsPerUnit.map(weightOf);

  let best = -1;
  scores.forEach((s, i) => { if (s > (best < 0 ? 0 : scores[best])) best = i; });
  const liveTerm = (k: string) => live.find((t) => t.key === k);
  if (best >= 0) {
    const keys = [...hitsPerUnit[best]].filter((k) => { const t = liveTerm(k); return t && meaningful(t); });
    const hasStrong = keys.some((k) => liveTerm(k)?.strong);
    if (keys.length >= 2 || (keys.length === 1 && hasStrong)) {
      // Grow into neighbours that carry a word of the claim, one silent unit may be bridged.
      const carries = (i: number) => !isHeading[i] && [...hitsPerUnit[i]].some((k) => { const t = liveTerm(k); return t && meaningful(t); });
      let from = best, to = best;
      for (let step = 0; step < GROW_STEPS; step++) {
        let grew = false;
        for (const dir of [-1, 1]) {
          let cand = (dir < 0 ? from : to) + dir;
          if (cand >= 0 && cand < units.length && !carries(cand)) cand += dir;
          if (cand < 0 || cand >= units.length || !carries(cand)) continue;
          const span = { start: units[Math.min(from, cand)].start, end: units[Math.max(to, cand)].end };
          if (span.end - span.start > PASSAGE_MAX_CHARS) continue;
          from = Math.min(from, cand);
          to = Math.max(to, cand);
          grew = true;
        }
        if (!grew) break;
      }
      return { kind: "passage", spans: [{ start: units[from].start, end: units[to].end }] };
    }
  }

  // No sentence stands out, so the strongest words are marked on their own.
  const pageToks = tokens(pageText);
  const spans: Span[] = [];
  const strongTerms = live.filter((t) => !t.fromTitle && (t.strong || (t.value == null && t.key.length >= 7)));
  for (const term of strongTerms) {
    const hits = termHits(term, pageToks);
    if (!hits.length || hits.length > 3) continue;
    for (const h of hits) spans.push({ start: h.start, end: h.end });
    if (spans.length >= MAX_KEYWORDS) break;
  }
  if (!spans.length) return null;
  spans.sort((a, b) => a.start - b.start);
  return { kind: "keywords", spans: spans.slice(0, MAX_KEYWORDS) };
}
