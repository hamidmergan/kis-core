// Pure transcript helpers, without React and therefore testable on their own.

export interface TimedCue {
  start: number;
  end: number;
}

/** The line a citation jump points at, via the exact segment start. */
export function cueIndexAtTime(cues: TimedCue[], time: number): number {
  if (cues.length === 0) return -1;
  // Lower bound: first cue whose start is >= time.
  let lo = 0, hi = cues.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (cues[mid].start < time) lo = mid + 1;
    else hi = mid;
  }
  const after = lo < cues.length ? lo : -1;   // nearest cue starting at/after time
  const before = lo - 1;                       // nearest cue starting before time (or -1)
  if (after === -1) return before;             // time is past every start
  if (before < 0) return after;                // time is at/before the first start
  const dAfter = cues[after].start - time;     // >= 0
  const dBefore = time - cues[before].start;   // > 0
  return dAfter <= dBefore ? after : before;
}

// The lines stay the truth, a paragraph is only a view of several.

export interface TextCue extends TimedCue {
  text: string;
}

export interface CueBlock {
  start: number;
  end: number;
  /** Index of the first cue in the block. */
  from: number;
  /** Index of the last cue in the block, inclusive. */
  to: number;
}

// The sizes come from a provider that already delivers paragraphs.

// A pause this long is the speaker starting something new, so the block ends with them.
const BLOCK_GAP_SEC = 1.5;
// Below this a block is not a paragraph yet, a sentence end does not close it.
const BLOCK_MIN_CHARS = 300;
// Two hard ceilings, in characters and in seconds.
const BLOCK_MAX_CHARS = 500;
const BLOCK_MAX_SEC = 30;

// Punctuation across writing systems, as characters instead of words.
const SENTENCE_END = /[.!?…。！？؟।॥։]["'”’»)\]]*$/u;

function endsSentence(text: string): boolean {
  return SENTENCE_END.test(text.trim());
}

// A sentence end anywhere in the text, not only at its very end. Scripts without
// spaces close a sentence with the mark alone, the others need a space behind it.
const SENTENCE_BREAK =
  /[\u3002\uff01\uff1f]["'\u201d\u2019\u00bb)\]\u300d\u300f]*|[.!?\u2026\u061f\u0964\u0965\u0589]["'\u201d\u2019\u00bb)\]]*(?=\s|$)/gu;

// How far the search may run when the cues carry no punctuation at all.
const SPAN_MAX_CUES = 6;

/** Where the running sentence starts and ends, cue borders included. */
export interface SentenceSpan {
  /** Index of the cue the sentence starts in. */
  fromIdx: number;
  /** Offset of its first character inside that cue. */
  fromChar: number;
  /** Index of the cue the sentence ends in. */
  toIdx: number;
  /** Offset just past its last character inside that cue. */
  toChar: number;
}

/** Offsets just past every sentence end inside the text. */
function sentenceBreaks(text: string): number[] {
  const out: number[] = [];
  SENTENCE_BREAK.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = SENTENCE_BREAK.exec(text)) !== null) out.push(m.index + m[0].length);
  return out;
}

/** The sentence a cue belongs to, so a mark can follow the sentence instead of the timed line. */
export function sentenceSpan(cues: { text: string }[], idx: number): SentenceSpan | null {
  if (idx < 0 || idx >= cues.length) return null;
  const at = (i: number) => (cues[i]?.text ?? "").trim();

  let fromIdx = idx;
  let fromChar = 0;
  while (fromIdx > 0 && idx - fromIdx < SPAN_MAX_CUES) {
    const prev = at(fromIdx - 1);
    const breaks = sentenceBreaks(prev);
    const last = breaks.length > 0 ? breaks[breaks.length - 1] : -1;
    if (last >= prev.length) break; // the cue before closes its sentence
    fromIdx -= 1;
    if (last < 0) { fromChar = 0; continue; }
    // The sentence starts inside that cue, behind the space after the punctuation.
    let start = last;
    while (start < prev.length && /\s/u.test(prev[start])) start += 1;
    fromChar = start;
    break;
  }

  let toIdx = idx;
  const own = at(idx);
  let toChar = own.length;
  const ownBreaks = sentenceBreaks(own);
  const closed = ownBreaks.length > 0 && ownBreaks[ownBreaks.length - 1] >= own.length;
  while (!closed && toIdx + 1 < cues.length && toIdx - idx < SPAN_MAX_CUES) {
    const next = at(toIdx + 1);
    const breaks = sentenceBreaks(next);
    toIdx += 1;
    if (breaks.length > 0) { toChar = breaks[0]; break; }
    toChar = next.length;
  }

  return { fromIdx, fromChar, toIdx, toChar };
}

/** Groups the lines into paragraphs, every line stays included exactly once. */
export function groupCues(cues: TextCue[]): CueBlock[] {
  const blocks: CueBlock[] = [];
  let from = 0;
  let chars = 0;

  const close = (to: number) => {
    blocks.push({ start: cues[from].start, end: cues[to].end, from, to });
    from = to + 1;
    chars = 0;
  };

  for (let i = 0; i < cues.length; i++) {
    const cue = cues[i];
    if (i > from) {
      const prev = cues[i - 1];
      const gap = cue.start - prev.end;
      const grownChars = chars + cue.text.length;
      const grownSec = cue.end - cues[from].start;
      const full = chars >= BLOCK_MIN_CHARS && endsSentence(prev.text);
      if (gap > BLOCK_GAP_SEC || grownChars > BLOCK_MAX_CHARS || grownSec > BLOCK_MAX_SEC || full) {
        close(i - 1);
      }
    }
    chars += cue.text.length;
  }
  if (cues.length > 0) close(cues.length - 1);
  return blocks;
}


/** Which transcript tracks are shown. */
export type TranscriptMode = "off" | "source" | "target" | "both";

/** The entries of the switcher, the original first and off last. */
export function buildTranscriptModes(
  { hasSource, hasTarget }: { hasSource: boolean; hasTarget: boolean },
): TranscriptMode[] {
  const modes: TranscriptMode[] = [];
  if (hasSource) modes.push("source");
  if (hasTarget) modes.push("target");
  if (hasSource && hasTarget) modes.push("both");
  modes.push("off");
  return modes;
}

/** The picker's last entry opens the language window instead of switching a track. */
export const TRANSLATE_ACTION = "__translate__";

export type TranscriptOption = TranscriptMode | typeof TRANSLATE_ACTION;

/** The picker entries, the plus for a new translation always sits last. */
export function buildTranscriptOptions(
  { hasSource, hasTarget, canTranslate }:
    { hasSource: boolean; hasTarget: boolean; canTranslate: boolean },
): TranscriptOption[] {
  const entries: TranscriptOption[] = buildTranscriptModes({ hasSource, hasTarget });
  if (canTranslate) entries.push(TRANSLATE_ACTION);
  return entries;
}

/** A translation started more than this long ago counts as lost. */
export const PENDING_TRANSLATION_TTL_MS = 10 * 60 * 1000;

/** The language a running translation waits for, null when there is none. */
export function readPendingTranslation(raw: string | null, now: number): string | null {
  if (!raw) return null;
  try {
    const note = JSON.parse(raw) as { ts?: number; lang?: string };
    if (typeof note?.lang !== "string" || typeof note?.ts !== "number") return null;
    return now - note.ts <= PENDING_TRANSLATION_TTL_MS ? note.lang : null;
  } catch {
    return null;
  }
}

export type TranslationProbe =
  | { kind: "done" }
  | { kind: "wait" }
  | { kind: "failed"; error: string };

/** What the poll answer means, an unreadable answer just keeps waiting. */
export function translationProbeOutcome(data: unknown): TranslationProbe {
  if (!data || typeof data !== "object") return { kind: "wait" };
  const { exists, error } = data as { exists?: unknown; error?: unknown };
  if (exists === true) return { kind: "done" };
  if (typeof error === "string") return { kind: "failed", error };
  return { kind: "wait" };
}

/** The languages offered for a translation, the recording's own is no target. */
export function chooseableTargetLangs(all: string[], sourceLang: string | null): string[] {
  const own = (sourceLang ?? "").toLowerCase();
  if (!own) return all;
  return all.filter((c) => c.toLowerCase() !== own);
}


// Which line of a cited spot carries the claim, a comparison instead of a search.

// Comparable words, without a stop word list and without stemming.
export function claimTokens(text: string): string[] {
  const words = text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .split(" ")
    .filter((w) => w.length >= 3 || /\p{N}/u.test(w));
  return [...new Set(words)];
}

// Compared as a substring, which replaces a stemmer.
export function claimOverlap(tokens: string[], line: string): number {
  if (tokens.length === 0) return 0;
  const hay = line.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ");
  let n = 0;
  for (const t of tokens) if (hay.includes(t)) n++;
  return n;
}

// Only words that are rare in this recording may help decide.
const COMMON_SHARE = 0.15;
const MIN_CORPUS_LINES = 8;

export function discriminatingTokens(tokens: string[], corpus: string[]): string[] {
  if (corpus.length < MIN_CORPUS_LINES) return tokens;
  const hays = corpus.map((l) => l.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " "));
  const limit = hays.length * COMMON_SHARE;
  return tokens.filter((t) => {
    let df = 0;
    for (const h of hays) if (h.includes(t) && ++df > limit) return false;
    return true;
  });
}

/** The line with the claim, or -1 when none clearly stands out. */
const MIN_CLAIM_TOKENS = 4;
const MIN_HITS = 3;
const DOMINANCE = 2;

export function claimLineIndex(claim: string, lines: string[], corpus?: string[]): number {
  if (lines.length < 2) return -1;
  const raw = claimTokens(claim);
  const tokens = corpus ? discriminatingTokens(raw, corpus) : raw;
  if (tokens.length < MIN_CLAIM_TOKENS) return -1;
  let best = -1, bestScore = 0, second = 0;
  lines.forEach((line, i) => {
    const score = claimOverlap(tokens, line);
    if (score > bestScore) { second = bestScore; bestScore = score; best = i; }
    else if (score > second) { second = score; }
  });
  return bestScore >= MIN_HITS && bestScore >= second * DOMINANCE ? best : -1;
}


// A word that occurs once in the whole transcript points at its spot.
const PIN_SHARE = 0.005;

// Rare alone is not enough, the word also has to be long enough.
const MIN_PIN_LEN = 9;

const _hay = (s: string) => s.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ");

/** All lines the claim rests on, empty when none stands out. */
export function claimLineIndices(claim: string, lines: string[], corpus?: string[]): number[] {
  const sieger = claimLineIndex(claim, lines, corpus);
  if (sieger < 0 || !corpus) return sieger < 0 ? [] : [sieger];
  const hays = corpus.map(_hay);
  const grenze = Math.max(1, hays.length * PIN_SHARE);
  const pins = discriminatingTokens(claimTokens(claim), corpus).filter((t) => {
    if (t.length < MIN_PIN_LEN) return false;
    let df = 0;
    for (const h of hays) if (h.includes(t) && ++df > grenze) return false;
    return true;
  });
  const beimSieger = _hay(lines[sieger]);
  const fehlend = pins.filter((t) => !beimSieger.includes(t));
  if (fehlend.length === 0) return [sieger];
  const raus = [sieger];
  lines.forEach((line, i) => {
    if (i === sieger) return;
    const h = _hay(line);
    if (fehlend.some((t) => h.includes(t))) raus.push(i);
  });
  return raus.sort((a, b) => a - b);
}


// --- Everything one citation jump points at ---------------------------------------------

export interface CitationFocus {
  /** First cue of the cited chunk, -1 when there are no cues yet. */
  idx: number;
  /** Last cue of the cited chunk. Equal to `idx` when no chunk end is known. */
  endIdx: number;
  /** The line inside the chunk carrying the claim, -1 when none stands out. */
  claimIdx: number;
  /** All carrying lines, empty means the whole section is highlighted. */
  claimIdxs: number[];
  /** The one cue everything points at: the claim line if there is one, else the chunk start. */
  focusIdx: number;
  /** Start of that cue, i.e. where the media has to play from. null when there is no focus. */
  focusTime: number | null;
}

/** One resolver for highlight, jump and play head. */
export function resolveCitationFocus(
  cues: TimedCue[],
  time: number,
  endTime: number | undefined,
  claim: string | undefined,
  corpus: string[],
  chunkStart?: number,
): CitationFocus {
  const timeIdx = cueIndexAtTime(cues, time);
  if (timeIdx < 0) {
    return { idx: -1, endIdx: -1, claimIdx: -1, claimIdxs: [], focusIdx: -1, focusTime: null };
  }
  // The whole chunk is highlighted, not only from the timestamp on.
  const idx = chunkStart != null ? cueIndexAtTime(cues, chunkStart) : timeIdx;
  const from = idx >= 0 ? Math.min(idx, timeIdx) : timeIdx;
  // Widened to every line that starts before the end of the chunk.
  let endIdx = Math.max(from, timeIdx);
  if (endTime != null) {
    while (endIdx + 1 < cues.length && cues[endIdx + 1].start < endTime - 0.05) endIdx++;
  }
  let claimIdx = -1;
  let claimIdxs: number[] = [];
  if (endIdx > from && claim) {
    const zeilen = corpus.slice(from, endIdx + 1);
    const rel = claimLineIndex(claim, zeilen, corpus);
    if (rel >= 0) {
      claimIdx = from + rel;
      claimIdxs = claimLineIndices(claim, zeilen, corpus).map((r) => from + r);
    }
  }
  // Without a carrying line the section stays highlighted, the jump goes to the timestamp.
  const focusIdx = claimIdx >= 0 ? claimIdx : timeIdx;
  return { idx: from, endIdx, claimIdx, claimIdxs, focusIdx, focusTime: cues[focusIdx]?.start ?? null };
}
