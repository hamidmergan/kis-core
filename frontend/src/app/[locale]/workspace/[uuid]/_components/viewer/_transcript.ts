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
 *   - the winner needs MARGIN more than the runner-up. A near-tie means the claim is spread
 *     across both lines, which is exactly when the block should stay evenly marked.
 */
const MIN_CLAIM_TOKENS = 4;
const MIN_HITS = 3;
const MARGIN = 2;

export function claimLineIndex(claim: string, lines: string[]): number {
  if (lines.length < 2) return -1;
  const tokens = claimTokens(claim);
  if (tokens.length < MIN_CLAIM_TOKENS) return -1;
  let best = -1, bestScore = 0, second = 0;
  lines.forEach((line, i) => {
    const score = claimOverlap(tokens, line);
    if (score > bestScore) { second = bestScore; bestScore = score; best = i; }
    else if (score > second) { second = score; }
  });
  return bestScore >= MIN_HITS && bestScore >= second + MARGIN ? best : -1;
}
