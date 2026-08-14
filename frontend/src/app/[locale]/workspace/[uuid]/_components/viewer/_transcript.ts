// Pure transcript helpers, kept React-free so they can be unit-tested in isolation
// (mirrors the _geometry.ts / _highlight.ts split in this folder).

export interface TimedCue {
  start: number;
  end: number;
}

/**
 * Index of the transcript segment to pin for a citation jump.
 *
 * `time` is the cited chunk's EXACT start (resolved from source_pages, a full float). A
 * chunk's start is a Whisper segment start, which is exactly a VTT cue start, so the cited
 * cue is simply the cue whose start is NEAREST to `time` — an exact hit save for millisecond
 * rounding between the stored float and the VTT timestamp. No flooring, no dependence on the
 * lossy whole-second display value, so a neighbouring cue can no longer be mis-picked. On a
 * tie, the cue at or after `time`. Returns -1 only for an empty list. O(log n); start-sorted.
 */
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

// --- Sentence-sized cues into readable blocks -------------------------------------------
//
// What a cue covers is the provider's decision, not ours: we hand Whisper's segments through
// untouched. myLab returns one short sentence per segment, which is right for subtitles
// running under a video but wrong for reading: the panel then shows forty rows of six words,
// each with its own timestamp, and the eye spends more time on the stamps than on the text.
//
// So the panel groups those cues into paragraphs. The cues stay the truth — they drive the
// subtitles, the citation jumps and the seek — and a block is only a view onto a RANGE of
// them, which is why it carries indices rather than text. Both language tracks share one
// grouping because both come from the same segments and therefore have identical timings.

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

// The sizes come from measuring what a paragraph-returning provider actually returns. On the
// same 30 seconds of German speech, KISSKI's whisper-large-v2 handed back ONE segment of 432
// characters over 27.2 seconds, while myLab's whisper-3-large returned nine of 52 characters
// on average. So a paragraph is roughly 300 to 500 characters, and that is what these say.
//
// KISSKI gets there by not deciding anything: its segment is just Whisper's 30-second window,
// which is why its cuts land wherever the window ends, sentence or no sentence. The rules below
// aim at the same size and cut better — at a pause, or at a sentence end, never in the middle
// of one unless a transcript without punctuation leaves no choice.

// A pause this long is the speaker starting something new, so the block ends with them.
const BLOCK_GAP_SEC = 1.5;
// Below this a block is not yet a paragraph, so a sentence ending inside it is not a reason
// to close it. Measured in characters, not seconds, because that is what reading length is.
const BLOCK_MIN_CHARS = 300;
// Two hard ceilings, for the case where the sentence never ends: a transcript without
// punctuation must not collapse into one wall of text. Seconds as well as characters,
// because sparse speech grows in time long before it grows in text. 500 characters is about
// 30 seconds of speech, so the two ceilings describe the same limit from two sides.
const BLOCK_MAX_CHARS = 500;
const BLOCK_MAX_SEC = 30;

// Sentence-final punctuation across the scripts a course can ship in. A list of CHARACTERS,
// not of words, so it stays language-agnostic: Latin full stop, question and exclamation
// marks, the ellipsis, their fullwidth CJK forms, plus the Arabic, Devanagari and Armenian
// equivalents. A closing quote or bracket may follow the mark.
const SENTENCE_END = /[.!?…。！？؟।॥։]["'”’»)\]]*$/u;

function endsSentence(text: string): boolean {
  return SENTENCE_END.test(text.trim());
}

/**
 * Group cues into paragraph-sized blocks.
 *
 * A block closes before the next cue when the speech pauses, when adding that cue would
 * push it past either ceiling, or when it is already long enough to read and the last cue
 * finished a sentence. A cue is never split, so cues that already arrive paragraph-sized
 * come back one block each and this is a no-op for them.
 *
 * The blocks are contiguous and cover every cue exactly once, in order.
 */
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


/**
 * Which transcript spurs are shown.
 * "source" = original media language, "target" = the owner-chosen translation,
 * "both" = stacked, "off" = nothing shown (listening comprehension).
 */
export type TranscriptMode = "off" | "source" | "target" | "both";

/**
 * The switcher's entries for a loaded source, in display order.
 *
 * The original always comes first and is the default the panel preselects. "both" needs
 * two distinct spurs. "off" is always offered and always last, so a student can hide the
 * text and just listen — even when only one language exists.
 */
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


// --- Which line of a cited passage carries the claim ------------------------------------
//
// A citation chip points at a retrieval CHUNK, and the chunk is the smallest thing the
// search knows: which sentence inside it produced the answer is recorded nowhere. With the
// current chunker a chunk runs about a minute, i.e. three to four transcript lines, so
// marking the whole chunk is correct but leaves the reader scanning ~160 spoken words for
// one date.
//
// The chunk's lines are already on screen and the answer sentence stands right next to the
// chip, so the pick is a comparison between three or four known candidates — NOT a search.
// That is the whole reason this is safe where the earlier grounding attempts were not: the
// worst case is emphasis on a neighbouring line INSIDE a block that stays correct, never a
// jump to the wrong place.

// Comparable tokens of a text. No stop-word list and no stemmer: those are per-language and
// this has to hold for every language a course ships in. Instead, drop tokens shorter than
// three characters, which removes most function words in alphabetic scripts, but KEEP short
// tokens containing a digit — "22" in "ab dem 22. April" is precisely the discriminating
// one. \p{L}/\p{N} so non-Latin scripts survive the strip.
export function claimTokens(text: string): string[] {
  const words = text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .split(" ")
    .filter((w) => w.length >= 3 || /\p{N}/u.test(w));
  return [...new Set(words)];
}

// How many distinct claim tokens the line contains. Substring, not equality: it lets
// "Sprechstunde" find "Sprechstunden" and "April" find "Aprils" without knowing a single
// rule of German — the cheap stand-in for a stemmer that works the same in any language.
export function claimOverlap(tokens: string[], line: string): number {
  if (tokens.length === 0) return 0;
  const hay = line.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ");
  let n = 0;
  for (const t of tokens) if (hay.includes(t)) n++;
  return n;
}

// Only tokens that are RARE in this recording say anything about which line a claim came
// from. The length rule alone does not get there: "die", "und", "dem", "wie", "bei" all
// clear three characters and every one of them counted as a hit, so a pick could be decided
// by five words that are in every second cue. Which words those are is per-language and per
// recording, so it is measured, not listed: a token sitting in more than COMMON_SHARE of the
// transcript's cues cannot discriminate between two of them and is dropped.
//
// Needs enough cues to measure against — in a handful of lines an ordinary content word
// easily clears any share — so below MIN_CORPUS_LINES the tokens are handed back untouched.
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

/**
 * The line of a cited passage that carries the claim, or -1 when none stands out.
 *
 * `lines` are the texts of the cited chunk's cues, in order; the returned index is relative
 * to that array. Returning -1 is the DEFAULT, not a failure: without a clear winner every
 * line keeps the same weight, because a guessed emphasis is worse than none — it sends the
 * reader to the wrong sentence with the same confidence as a right one.
 *
 * Three conditions, each of which exists because dropping it produced a confident wrong
 * pick in testing:
 *   - the claim needs MIN_CLAIM_TOKENS of its own. Dropping short words catches most
 *     function words but not all of them ("das", "ist", "und" survive the length rule in
 *     German), so a three-word claim can win a line on function words alone.
 *   - the winner needs MIN_HITS distinct matches, so one accidental word is not a verdict.
 *   - the winner needs DOMINANCE times the runner-up. Anything less means the claim is spread
 *     across the lines, which is exactly when the block should stay evenly marked.
 *
 * `corpus` is every cue of the transcript. Given it, only words that are rare in this
 * recording get to vote (see discriminatingTokens), which is what makes those counts mean
 * anything at all.
 *
 * Both numbers come from measuring the real recording rather than from taste. A claim
 * summarising two lines at once scored 6 against 4 on the lines it summarised; a claim resting
 * on one date scored 3 against 0 and 4 against 0. "One or two hits ahead" cannot separate
 * those, "twice as much" separates them with room to spare. Before the rare-word filter even
 * the ratio could not: the same two cases were 11:8 and 5:3, i.e. both around 1.5.
 */
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


// --- Everything one citation jump points at ---------------------------------------------

export interface CitationFocus {
  /** First cue of the cited chunk, -1 when there are no cues yet. */
  idx: number;
  /** Last cue of the cited chunk. Equal to `idx` when no chunk end is known. */
  endIdx: number;
  /** The line inside the chunk carrying the claim, -1 when none stands out. */
  claimIdx: number;
  /** The one cue everything points at: the claim line if there is one, else the chunk start. */
  focusIdx: number;
  /** Start of that cue, i.e. where the media has to play from. null when there is no focus. */
  focusTime: number | null;
}

/**
 * Resolve a citation jump to the ONE cue the marking, the scroll AND the play head share.
 *
 * The chip carries the chunk's start, but a chunk runs about a minute and the sentence the
 * answer rests on is regularly a line or two further down. The marking already followed that
 * line while the seek kept using the chunk start, so the yellow marking and the playing line
 * sat in two different paragraphs — the reported bug. One resolver, one target, no drift.
 *
 * `corpus` is the whole transcript, one entry per cue, both language tracks joined; the
 * cited span is simply its slice. It is also the yardstick for which words are common in
 * THIS recording and therefore say nothing about which line a claim came from.
 */
export function resolveCitationFocus(
  cues: TimedCue[],
  time: number,
  endTime: number | undefined,
  claim: string | undefined,
  corpus: string[],
): CitationFocus {
  const idx = cueIndexAtTime(cues, time);
  if (idx < 0) return { idx: -1, endIdx: -1, claimIdx: -1, focusIdx: -1, focusTime: null };
  // Widen to every cue that STARTS before the chunk ends, so the marking covers the cited
  // passage rather than its first few seconds. The small guard keeps a cue that begins
  // exactly at the chunk's end out of it.
  let endIdx = idx;
  if (endTime != null) {
    while (endIdx + 1 < cues.length && cues[endIdx + 1].start < endTime - 0.05) endIdx++;
  }
  let claimIdx = -1;
  if (endIdx > idx && claim) {
    const rel = claimLineIndex(claim, corpus.slice(idx, endIdx + 1), corpus);
    if (rel >= 0) claimIdx = idx + rel;
  }
  const focusIdx = claimIdx >= 0 ? claimIdx : idx;
  return { idx, endIdx, claimIdx, focusIdx, focusTime: cues[focusIdx]?.start ?? null };
}
