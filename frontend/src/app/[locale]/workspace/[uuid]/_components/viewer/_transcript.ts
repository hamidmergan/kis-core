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
