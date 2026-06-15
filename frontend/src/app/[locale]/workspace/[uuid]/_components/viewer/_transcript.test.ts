import { describe, it, expect } from "vitest";
import { cueIndexAtTime, type TimedCue } from "./_transcript";

// `time` is now the chunk's EXACT start (a Whisper segment start, i.e. a VTT cue start),
// resolved from source_pages — NOT the lossy whole-second display timestamp.
const cues: TimedCue[] = [
  { start: 0.0, end: 5.0 },     // 0
  { start: 5.2, end: 10.0 },    // 1
  { start: 12.5, end: 18.0 },   // 2
  { start: 18.0, end: 25.0 },   // 3
];

describe("cueIndexAtTime", () => {
  it("returns -1 only when there are no cues", () => {
    expect(cueIndexAtTime([], 3)).toBe(-1);
  });

  it("lands exactly on the cue with that start", () => {
    expect(cueIndexAtTime(cues, 5.2)).toBe(1);
    expect(cueIndexAtTime(cues, 12.5)).toBe(2);
    expect(cueIndexAtTime(cues, 0.0)).toBe(0);
    expect(cueIndexAtTime(cues, 18.0)).toBe(3);
  });

  it("tolerates millisecond rounding between the DB float and the VTT cue start", () => {
    // DB start 5.234, VTT wrote 5.2 -> nearest start still resolves to that cue, not a neighbour.
    expect(cueIndexAtTime(cues, 5.234)).toBe(1);
    expect(cueIndexAtTime(cues, 12.49)).toBe(2);
  });

  it("returns the covering cue for a time inside it", () => {
    expect(cueIndexAtTime(cues, 7)).toBe(1);
    expect(cueIndexAtTime(cues, 20)).toBe(3);
  });

  it("clamps a time past the last cue to the last cue", () => {
    expect(cueIndexAtTime(cues, 999)).toBe(3);
  });

  it("pins the first cue for a time before the first start", () => {
    expect(cueIndexAtTime(cues, -1)).toBe(0);
  });

  // The case that fooled the floored-second heuristics: a SHORT preceding cue whose start
  // (475.5) is numerically near the cited cue. With the EXACT start there is no ambiguity —
  // the cited cue's own start matches.
  it("pins the exact cue, unfooled by a numerically near short preceding cue", () => {
    const vtt: TimedCue[] = [
      { start: 470.00, end: 475.50 },  // 0
      { start: 475.50, end: 476.99 },  // 1  short
      { start: 476.99, end: 492.00 },  // 2  cited, exact start 476.99
    ];
    expect(cueIndexAtTime(vtt, 476.99)).toBe(2);
  });
});
