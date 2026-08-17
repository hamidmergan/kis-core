import { describe, it, expect } from "vitest";
import { buildTranscriptModes, claimLineIndex, claimLineIndices, claimOverlap, claimTokens, cueIndexAtTime, groupCues, resolveCitationFocus, type TextCue, type TimedCue } from "./_transcript";

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

describe("resolveCitationFocus — marking and play head land on the same line", () => {
  // Verbatim from the reported case: the chip said 02:59, the video played 02:59, and the
  // yellow marking sat on the line at 03:17. Two cues, one chunk, two different targets.
  const line0 = "Was Sie weglassen sollen, sind Inhaltsabbildungs- und Tabellenverzeichnis. "
    + "Und die Inhalte dieser sechs bis sieben Seiten sollen, wenn Sie sich die Vorlage schon "
    + "angeschaut haben, haben Sie vielleicht schon ein, zwei Dinge gesehen. Das erste soll "
    + "ein Abstract sein, was alles zusammenfasst.";
  const line1 = "Das ist natürlich dann auch etwas, was man ein bisschen später schreibt, je "
    + "nachdem, wie weit man ist. Dann sollen Sie eine Einleitung oder Motivation für Ihre "
    + "Forschungsfrage beschreiben, definieren. Dann sollen Sie die Grundlagen beschreiben.";
  const claim = "Die Arbeit soll ein Abstract, eine Einleitung mit Forschungsfrage und "
    + "Grundlagen zum aktuellen Stand der Forschung enthalten.";

  // Stands in for the rest of the recording, so the common-word filter has something to
  // measure against (below MIN_CORPUS_LINES nothing is dropped).
  const filler = Array.from({ length: 20 }, (_, i) =>
    `Und dann gibt es, wie gesagt, bei dem Punkt ${i} von die Sache und das war es.`);
  const corpus = [...filler, line0, line1];
  const cues: TimedCue[] = [
    ...Array.from({ length: 20 }, (_, i) => ({ start: i * 5, end: i * 5 + 4 })),
    { start: 179.0, end: 197.0 },  // 20 — the chunk starts here, and so does the chip
    { start: 197.0, end: 211.0 },  // 21 — the line the answer actually rests on
  ];

  it("seeks to the marked line, not to the chunk start one cue before it", () => {
    const focus = resolveCitationFocus(cues, 179.0, 211.0, claim, corpus);
    expect(focus.idx).toBe(20);
    expect(focus.endIdx).toBe(21);
    expect(focus.claimIdx).toBe(21);
    // The one that was broken: marking and play head must name the same cue.
    expect(focus.focusIdx).toBe(21);
    expect(focus.focusTime).toBe(197.0);
  });

  it("stays on the chunk start when no line stands out", () => {
    // A claim summarising the whole passage marks all of it, so there is nothing to seek to
    // but its beginning — exactly where the chip points.
    const spread = "Die Inhalte der Seiten und die Vorlage und das Abstract und die "
      + "Einleitung und die Grundlagen gehören alle dazu.";
    const focus = resolveCitationFocus(cues, 179.0, 211.0, spread, corpus);
    expect(focus.claimIdx).toBe(-1);
    expect(focus.focusIdx).toBe(20);
    expect(focus.focusTime).toBe(179.0);
  });

  it("marks the single cue when the chunk has no end", () => {
    // Older messages carry no end_time, so there is no span to rank lines in.
    const focus = resolveCitationFocus(cues, 179.0, undefined, claim, corpus);
    expect(focus.endIdx).toBe(20);
    expect(focus.claimIdx).toBe(-1);
    expect(focus.focusTime).toBe(179.0);
  });

  it("points at nothing while the cues are still missing", () => {
    const focus = resolveCitationFocus([], 179.0, 211.0, claim, corpus);
    expect(focus).toEqual({ idx: -1, endIdx: -1, claimIdx: -1, claimIdxs: [], focusIdx: -1, focusTime: null });
  });

  // Die Zeitmarke des Chips ist seit aia_segment_pick nicht mehr der Chunk-Anfang, sondern
  // die beste Vermutung, wo im Chunk die Aussage faellt. Sie liegt also mitten im Chunk.
  describe("Zeitmarke mitten im Chunk", () => {
    // Wie oben, aber die Aussage stammt aus der ERSTEN Zeile, waehrend der Chip auf die
    // zweite zeigt. Das ist der Fall, den die Verbreiterung rettet.
    const claimAusZeile0 = "Inhaltsabbildungs- und Tabellenverzeichnis sollen weggelassen "
      + "werden, in der Vorlage steht als erstes ein Abstract.";

    it("markiert ab dem Chunk-Anfang, nicht ab der Zeitmarke", () => {
      const focus = resolveCitationFocus(cues, 197.0, 211.0, claimAusZeile0, corpus, 179.0);
      expect(focus.idx).toBe(20);        // Chunk-Anfang, nicht 21
      expect(focus.endIdx).toBe(21);
    });

    it("findet die tragende Zeile auch VOR der Zeitmarke", () => {
      const focus = resolveCitationFocus(cues, 197.0, 211.0, claimAusZeile0, corpus, 179.0);
      expect(focus.claimIdx).toBe(20);
      expect(focus.focusTime).toBe(179.0);
    });

    it("ohne Chunk-Anfang bleibt die Zeile davor unerreichbar", () => {
      // Der Bestand vor der Aenderung: ab der Zeitmarke markiert, davor nichts. Steht der
      // belegende Satz frueher, faellt er aus der Markierung heraus.
      const focus = resolveCitationFocus(cues, 197.0, 211.0, claimAusZeile0, corpus);
      expect(focus.idx).toBe(21);
      expect(focus.claimIdx).toBe(-1);
    });

    it("ohne tragende Zeile bleibt der ganze Chunk markiert und der Player auf der Vermutung", () => {
      const spread = "Die Inhalte der Seiten und die Vorlage und das Abstract und die "
        + "Einleitung und die Grundlagen gehören alle dazu.";
      const focus = resolveCitationFocus(cues, 197.0, 211.0, spread, corpus, 179.0);
      expect(focus.claimIdx).toBe(-1);
      expect(focus.idx).toBe(20);          // markiert wird der ganze Chunk
      expect(focus.endIdx).toBe(21);
      expect(focus.focusIdx).toBe(21);     // angesteuert wird die Zeitmarke des Chips
      expect(focus.focusTime).toBe(197.0);
    });
  });
});

describe("groupCues — sentence-sized cues into readable blocks", () => {
  // A cue of `sec` seconds starting at `start`, whose text is `chars` long. Ends the
  // sentence unless told otherwise, because that is what a Whisper segment usually does.
  const cue = (start: number, sec: number, chars: number, ends = true): TextCue => ({
    start,
    end: start + sec,
    text: "w".repeat(Math.max(1, chars - 1)) + (ends ? "." : ","),
  });

  it("returns nothing for an empty transcript", () => {
    expect(groupCues([])).toEqual([]);
  });

  it("merges sentences that are far too short to stand alone", () => {
    // Four four-second lines of 30 characters: 16s and 120 characters in total, which is
    // one paragraph, not four rows.
    const cues = [cue(0, 4, 30), cue(4, 4, 30), cue(8, 4, 30), cue(12, 4, 30)];
    expect(groupCues(cues)).toEqual([{ start: 0, end: 16, from: 0, to: 3 }]);
  });

  it("starts a new block after a real pause in the speech", () => {
    const cues = [cue(0, 4, 30), cue(4, 4, 30), cue(20, 4, 30)];
    const blocks = groupCues(cues);
    expect(blocks.map((b) => [b.from, b.to])).toEqual([[0, 1], [2, 2]]);
  });

  it("closes a full block at the end of a sentence, not mid-sentence", () => {
    // Cue 4 fills the block to 300 characters, the reading length a paragraph is meant to
    // have, and its text ends a sentence. So the block closes there and cue 5 opens the next.
    const cues = Array.from({ length: 8 }, (_, i) => cue(i * 3, 3, 60));
    expect(groupCues(cues).map((b) => [b.from, b.to])).toEqual([[0, 4], [5, 7]]);
  });

  it("does not break a sentence that runs across several cues", () => {
    // Only the last cue ends the sentence, so the block cannot close before it even though
    // it passed the minimum length two cues ago.
    const cues = Array.from({ length: 6 }, (_, i) => cue(i * 3, 3, 60, i === 5));
    expect(groupCues(cues).map((b) => [b.from, b.to])).toEqual([[0, 5]]);
  });

  it("cuts a block that never ends a sentence rather than letting it grow forever", () => {
    // Ten cues of 5s, none of them ending a sentence: without a hard ceiling this would be
    // one 50-second wall of text.
    const cues = Array.from({ length: 10 }, (_, i) => cue(i * 5, 5, 30, false));
    const blocks = groupCues(cues);
    expect(blocks.length).toBeGreaterThan(1);
    for (const b of blocks) expect(b.end - b.start).toBeLessThanOrEqual(30);
  });

  it("cuts a block that grows too long to read even while sentences run on", () => {
    // Short in time, huge in text: three 200-character cues in nine seconds.
    const cues = [cue(0, 3, 200, false), cue(3, 3, 200, false), cue(6, 3, 200, false)];
    const blocks = groupCues(cues);
    expect(blocks.length).toBeGreaterThan(1);
  });

  it("leaves cues that are already block-sized alone", () => {
    // What a provider returning paragraphs already delivers. Grouping must not glue two of
    // them together, so the same function is a no-op there.
    const cues = [cue(0, 40, 300), cue(40, 40, 300), cue(80, 40, 300)];
    expect(groupCues(cues).map((b) => [b.from, b.to])).toEqual([[0, 0], [1, 1], [2, 2]]);
  });

  it("ends a sentence on a script that does not use the full stop", () => {
    // Same shape as the block above, only the sentence ends on the ideographic full stop.
    // If that character did not count, all four cues would end up in one block.
    const jp = (start: number): TextCue => ({
      start, end: start + 5, text: "あ".repeat(59) + "。",
    });
    const cues = [jp(0), jp(5), jp(10), jp(15), jp(20), jp(25)];
    expect(groupCues(cues).map((b) => [b.from, b.to])).toEqual([[0, 4], [5, 5]]);
  });

  it("covers every cue exactly once, in order", () => {
    const cues = Array.from({ length: 40 }, (_, i) => cue(i * 4, 4, 50, i % 3 === 0));
    const blocks = groupCues(cues);
    expect(blocks[0].from).toBe(0);
    expect(blocks[blocks.length - 1].to).toBe(cues.length - 1);
    for (let i = 1; i < blocks.length; i++) expect(blocks[i].from).toBe(blocks[i - 1].to + 1);
  });

  it("takes its times from the cues it spans", () => {
    const cues = [cue(1.5, 4, 30), cue(5.5, 4, 30)];
    expect(groupCues(cues)).toEqual([{ start: 1.5, end: 9.5, from: 0, to: 1 }]);
  });

  // Measured, not invented: this is verbatim what THL myLab (whisper-3-large) returned for a
  // 30-second German recording — nine segments of two to five seconds. KISSKI's whisper handed
  // back the SAME audio as two segments, the first 432 characters over 27 seconds, and that is
  // the paragraph size this is tuned to. So the numbers are pinned here: change a constant and
  // this test says what it does to a real transcript.
  it("turns a real myLab transcript into KISSKI-sized paragraphs", () => {
    const cues: TextCue[] = [
      { start: 0.00, end: 4.46, text: "Herzlich willkommen zur Einführungskonferenz im wissenschaftlichen Seminar." },
      { start: 4.78, end: 9.52, text: "Mein Name ist Lenka Kleinau. Ich bin die Mentorin und Tutorin in diesem Kurs." },
      { start: 9.84, end: 13.74, text: "Es ist nicht das erste Mal, dass ich als Lehrperson tätig bin." },
      { start: 14.08, end: 16.76, text: "Der Kurs bereitet Sie auf die Masterarbeit vor." },
      { start: 17.08, end: 19.38, text: "Wir treffen uns jeden Mittwoch um halb sechs." },
      { start: 19.68, end: 24.10, text: "Die Prüfungsleistung besteht aus einer Hausarbeit und einer Präsentation." },
      { start: 24.50, end: 27.06, text: "Die Hausarbeit umfasst sechs bis sieben Seiten." },
      { start: 27.06, end: 29.30, text: "Bitte nutzen Sie die Vorlage in Word." },
      { start: 29.30, end: 30.30, text: "oder Latex." },
    ];
    // Two paragraphs of 306 and 168 characters, cut where KISSKI cut it too — except that the
    // stray "oder Latex." no longer stands alone: it is the tail of the sentence before it.
    expect(groupCues(cues).map((b) => [b.from, b.to])).toEqual([[0, 4], [5, 8]]);
  });
});


// Wortgetreu aus 2026-06-15.mp4, Chunk 45:01-46:30. Der Antwortsatz nennt ZWEI Dinge aus
// zwei Momenten: die Fragestunde und die affinen Chiffren. Markiert war nur der zweite,
// weil seine Zeile vier Anspruchswoerter traegt und die andere zwei — "noch" zaehlte dabei
// so viel wie "Schifren". Die Zeile mit der Fragestunde stand unmarkiert daneben, und das
// liest sich, als stuende sie nicht in der Quelle.


// Wortgetreu aus 2026-06-15.mp4, Chunk 45:01-46:30. Der Antwortsatz nennt ZWEI Dinge aus
// zwei Momenten: die Fragestunde und die affinen Chiffren. Markiert war nur der zweite,
// weil seine Zeile drei Anspruchswoerter traegt und die andere eines. Die Zeile mit der
// Fragestunde stand unmarkiert daneben, und das liest sich, als stuende sie nicht in der
// Quelle.
describe("claimLineIndices — ein Satz aus zwei Momenten", () => {
  const spanne = [
    "Also nochmals",
    "zur Klausur, also in der Klausur kommt",
    "ja nichts dran, was wir nicht irgendwie",
    "auch vorbereitet",
    "haben, also da kommt nicht irgendwas ganz anderes",
    "dran, aber insofern",
    "kommen ja auch eine ganze Reihe von",
    "Aufgaben dran, acht Aufgaben, man hat ja schon mal",
    "neun Aufgaben dran bekommen",
    "die müssen",
    "auch geübt werden.",
    "Wir machen nächste Woche noch affine Schifren.",
    "Dann haben wir noch Zeit, da machen wir noch eine Fragestunde.",
    "Da können Sie sich noch mal die Sachen angucken.",
  ];
  // Fuellmaterial mit dem Fuellwortschatz einer echten Vorlesung, damit der
  // Haeufigkeitsfilter "noch", "eine", "der" und "werden" als gaengig erkennt. Ohne das
  // waeren sie im Testkorpus selten und wuerden mitentscheiden.
  const fueller = Array.from({ length: 60 }, (_, i) =>
    `Und dann ist das noch eine Sache von der Art ${i}, die wir uns dann ansehen werden.`);
  const korpus = [...fueller, ...spanne];
  const claim = "Ja, laut einer Aufzeichnung wird eine Fragestunde durchgeführt, nachdem "
    + "in der darauffolgenden Woche noch affine Schifren behandelt wurden";

  it("waehlt weiterhin die staerkste Zeile", () => {
    expect(claimLineIndex(claim, spanne, korpus)).toBe(11);
  });

  it("nimmt die Zeile mit dem fehlenden Pin-Wort dazu", () => {
    expect(claimLineIndices(claim, spanne, korpus)).toEqual([11, 12]);
  });

  it("laesst die uebrigen Zeilen in Ruhe", () => {
    const raus = claimLineIndices(claim, spanne, korpus);
    expect(raus).not.toContain(0);
    expect(raus).not.toContain(13);
  });

  it("bleibt bei einer Zeile, wenn ihr kein Pin-Wort fehlt", () => {
    const nurEins = "In der darauffolgenden Woche werden noch affine Schifren behandelt.";
    expect(claimLineIndices(nurEins, spanne, korpus)).toEqual([11]);
  });

  it("ein haeufiges Wort zieht keine Zeile herein", () => {
    // "noch" steht in Zeile 0 ("Also nochmals") und in fast jeder Fuellzeile. Haeufige
    // Woerter duerfen nicht zaehlen, sonst haengt an jedem Beleg der halbe Chunk.
    expect(claimLineIndices(claim, spanne, korpus)).not.toContain(0);
  });

  it("ohne Sieger bleibt die Liste leer, der ganze Abschnitt wird markiert", () => {
    expect(claimLineIndices("Das ist so.", spanne, korpus)).toEqual([]);
  });

  it("ein kurzes Wort zieht keine Zeile herein, auch wenn es selten ist", () => {
    // "geübt" steht in genau einer Zeile der Spanne und sonst nirgends, ist also selten —
    // sagt aber nichts. Genau daran haengt die Laengenregel: an 139 echten Belegen zogen
    // "wurden", "stellt" und "logische" Zeilen herein, die nichts mit der Aussage zu tun
    // hatten. "stellt" traf dabei mitten in "hochgestellt", weil der Abgleich absichtlich
    // eine Teilzeichenkette ist (damit "Sprechstunde" auch "Sprechstunden" findet).
    const kurz = "In der Woche werden noch affine Schifren geübt.";
    expect(claimLineIndices(kurz, spanne, korpus)).toEqual([11]);
  });
});
