import { describe, it, expect } from "vitest";
import { buildTranscriptModes, claimLineIndex, claimOverlap, claimTokens, cueIndexAtTime, type TimedCue } from "./_transcript";

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

describe("buildTranscriptModes", () => {
  it("offers the original plus off when only the source track loaded", () => {
    expect(buildTranscriptModes({ hasSource: true, hasTarget: false })).toEqual(["source", "off"]);
  });

  it("offers original, translation, both and off when both tracks loaded", () => {
    expect(buildTranscriptModes({ hasSource: true, hasTarget: true })).toEqual([
      "source",
      "target",
      "both",
      "off",
    ]);
  });

  it("offers the translation plus off when the source track is missing", () => {
    expect(buildTranscriptModes({ hasSource: false, hasTarget: true })).toEqual(["target", "off"]);
  });

  // The panel bails out before rendering when no track loaded at all, but the helper
  // stays total so it can never hand back an empty list.
  it("still offers off when no track loaded", () => {
    expect(buildTranscriptModes({ hasSource: false, hasTarget: false })).toEqual(["off"]);
  });

  it("always puts off last", () => {
    for (const hasSource of [true, false]) {
      for (const hasTarget of [true, false]) {
        const modes = buildTranscriptModes({ hasSource, hasTarget });
        expect(modes[modes.length - 1]).toBe("off");
      }
    }
  });
});

describe("claimLineIndex — which line of a cited passage carries the claim", () => {
  // Verbatim from the reported case: the chip cited the chunk 48:11-48:56, whose two
  // transcript lines are these. The date the answer rests on sits in the SECOND one.
  const line1 = "spezieller darauf ein und vielleicht rufen wir dann noch so ein paar Dinge ins "
    + "Gedächtnis. Wie gesagt, hier ist das in der Masterarbeit dann, worauf sie ja das "
    + "wissenschaftliche Seminar vorbereiten soll, ist das auf jeden Fall ein sehr wichtiges "
    + "Kriterium, dass sie das erfüllen.";
  const line2 = "Und dann ab dem 22. April wird es, wie schon vorhin besprochen, offene "
    + "Sprechstunden geben. Und alles Weitere, wann die Peer Reviews stattfinden sollen und so "
    + "weiter und so fort, können Sie nochmal im Kursplan nachschauen.";

  it("picks the line holding the date, not the one the timestamp starts at", () => {
    const claim = "Der Kontakt läuft über das Fachforum sowie eine wöchentliche Sprechstunde, "
      + "die ab dem 22. April wöchentlich stattfindet";
    expect(claimLineIndex(claim, [line1, line2])).toBe(1);
  });

  it("matches across inflection without knowing any German", () => {
    // "Sprechstunde" must find "Sprechstunden" — substring, no stemmer, no word list.
    expect(claimOverlap(claimTokens("offene Sprechstunde"), line2)).toBeGreaterThan(0);
  });

  it("keeps the digits of a date, which are the discriminating token", () => {
    expect(claimTokens("ab dem 22. April")).toContain("22");
  });

  it("stays out of it when the claim is too thin to decide", () => {
    // "das"/"ist" survive the length rule and both sit in line1, which would hand it a
    // confident win on function words alone. A claim this short may not decide anything.
    expect(claimLineIndex("Das ist so.", [line1, line2])).toBe(-1);
  });

  it("stays out of it on a tie, when the claim is spread over both lines", () => {
    const both = "Das wissenschaftliche Seminar hat ein wichtiges Kriterium erfüllt";
    const a = "Das wissenschaftliche Seminar hat ein wichtiges Kriterium.";
    expect(claimLineIndex(both, [a, a])).toBe(-1);
  });

  it("does not emphasise anything when the passage is a single line", () => {
    expect(claimLineIndex("ab dem 22. April", [line2])).toBe(-1);
  });

  it("survives a script without spaces instead of guessing", () => {
    // CJK has no word boundaries, so tokenising yields one long token that matches nothing
    // or everything. Either way the guard decides: no clear winner, no emphasis.
    expect(claimLineIndex("四月二十二日", ["二十二", "別の行"])).toBe(-1);
  });
});

describe("claimLineIndex — a summarising claim must not pick a line", () => {
  // The second reported case, verbatim from the recording (cues 14:01 and 14:24). The chip
  // pointed at the first line, the marking landed on the second, and the reader saw the blue
  // playing line and the yellow marking sitting on two different places.
  //
  // Both lines carry half of the answer sentence: "Extended Abstract" and "Abgabe" are in the
  // first, "zwei Seiten" and "Peer-Review" in the second. Neither may win.
  const line1 = "Ende Mai, genau, da ist die freiwillige Abgabe. Da würden sie quasi in dem "
    + "Extended Abstract beschreiben, wie weit sie gekommen sind. Also das muss noch gar nicht "
    + "fertig sein oder so. Sie haben ja Zeit bis Anfang Juli quasi alles zu machen. Das heißt, "
    + "das Extended Abstract würde das umfassen, was sie bis dahin recherchiert haben, was sie "
    + "bis dahin herausgefunden haben, sag ich mal.";
  const line2 = "Und das soll so ungefähr zwei Seiten lang sein, zusätzlich zum "
    + "Literaturverzeichnis. Und danach würde eigentlich so ein Peer-Review-Prozess folgen, "
    + "während der ersten Präsenz. Aber die beiden Punkte, wie gesagt, sind freiwillig. Die "
    + "waren früher Bestandteil der Prüfungsvorleistung. Aber die sind sehr hilfreich und "
    + "deswegen habe ich sie hier noch drin gelassen. Zwar ist freiwillige Punkte, aber ja, "
    + "trotzdem wichtig.";
  const claim = "Zusätzlich gibt es freiwillige Angebote zur Unterstützung, wie die Abgabe einer "
    + "Ideenskizze (Extended Abstract) von etwa zwei Seiten und die Teilnahme an einem "
    + "Peer-Review-Verfahren, bei dem Studierende gegenseitig Feedback geben";

  // Stands in for the other 135 cues of that recording: the filler words recur throughout, the
  // words carrying the claim appear nowhere else.
  const filler = Array.from({ length: 20 }, (_, i) =>
    `Und dann gibt es, wie gesagt, bei dem Punkt ${i} von die Sache und das war es.`);
  const corpus = [...filler, line1, line2];

  it("leaves the whole passage marked when the claim summarises all of it", () => {
    // Measured on the real transcript: 6 against 4 once the common words are out. One line
    // being half again as full as the other is not a line standing out.
    expect(claimLineIndex(claim, [line1, line2], corpus)).toBe(-1);
  });

  it("still picks the line that really does stand out", () => {
    // Measured on the same recording: 3 against 0 for the date the answer rested on.
    const dateLine = "Und dann ab dem 22. April wird es offene Sprechstunden geben.";
    const otherLine = "Und dann gibt es, wie gesagt, bei dem Punkt von die Sache und das war es.";
    const dateClaim = "Der Kontakt läuft über eine wöchentliche Sprechstunde, die ab dem 22. April stattfindet";
    expect(claimLineIndex(dateClaim, [otherLine, dateLine], [...filler, otherLine, dateLine])).toBe(1);
  });

  it("keeps its hands off when the recording is too short to say what is common", () => {
    // Under MIN_CORPUS_LINES nothing is dropped, so every filler word still counts and the
    // scores stay too close for anything to win. Never a confident pick on thin evidence.
    expect(claimLineIndex(claim, [line1, line2], [line1, line2])).toBe(-1);
  });
});
