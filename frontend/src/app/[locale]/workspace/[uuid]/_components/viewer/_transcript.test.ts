import { describe, it, expect } from "vitest";
import { buildTranscriptModes, buildTranscriptOptions, chooseableTargetLangs, readPendingTranslation, translationProbeOutcome, TRANSLATE_ACTION, claimLineIndex, claimLineIndices, claimOverlap, claimTokens, cueIndexAtTime, groupCues, resolveCitationFocus, sentenceSpan, type TextCue, type TimedCue } from "./_transcript";

// The time is the exact segment start, not the rounded display.
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

  // With the exact start there is no confusion any more.
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

  // The helper stays complete and never returns an empty list.
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
  // Verbatim from the reported case, the claim sits in the second line.
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
    // A very short claim must decide nothing.
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
    // Without word boundaries the guard decides: no clear winner, no emphasis.
    expect(claimLineIndex("四月二十二日", ["二十二", "別の行"])).toBe(-1);
  });
});

describe("claimLineIndex — a summarising claim must not pick a line", () => {
  // Both lines carry half the claim, neither may win.
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

  // Stands for the remaining lines of the recording so frequency becomes measurable.
  const filler = Array.from({ length: 20 }, (_, i) =>
    `Und dann gibt es, wie gesagt, bei dem Punkt ${i} von die Sache und das war es.`);
  const corpus = [...filler, line1, line2];

  it("leaves the whole passage marked when the claim summarises all of it", () => {
    // A line that is only half as full does not stand out.
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
    // On thin evidence never a confident hit.
    expect(claimLineIndex(claim, [line1, line2], [line1, line2])).toBe(-1);
  });
});

describe("resolveCitationFocus — marking and play head land on the same line", () => {
  // Verbatim from the reported case: two lines, two different targets.
  const line0 = "Was Sie weglassen sollen, sind Inhaltsabbildungs- und Tabellenverzeichnis. "
    + "Und die Inhalte dieser sechs bis sieben Seiten sollen, wenn Sie sich die Vorlage schon "
    + "angeschaut haben, haben Sie vielleicht schon ein, zwei Dinge gesehen. Das erste soll "
    + "ein Abstract sein, was alles zusammenfasst.";
  const line1 = "Das ist natürlich dann auch etwas, was man ein bisschen später schreibt, je "
    + "nachdem, wie weit man ist. Dann sollen Sie eine Einleitung oder Motivation für Ihre "
    + "Forschungsfrage beschreiben, definieren. Dann sollen Sie die Grundlagen beschreiben.";
  const claim = "Die Arbeit soll ein Abstract, eine Einleitung mit Forschungsfrage und "
    + "Grundlagen zum aktuellen Stand der Forschung enthalten.";

  // Stands for the rest of the recording so the frequency filter applies.
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
    // A claim about the whole spot marks everything, the jump goes to the start.
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

  // The chip's timestamp now sits in the middle of the chunk.
  describe("Zeitmarke mitten im Chunk", () => {
    // The claim is in the first line, the chip points at the second.
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
      // Highlighting used to start at the timestamp, everything before fell out.
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
  // Builds a line with a length and a duration, it ends the sentence.
  const cue = (start: number, sec: number, chars: number, ends = true): TextCue => ({
    start,
    end: start + sec,
    text: "w".repeat(Math.max(1, chars - 1)) + (ends ? "." : ","),
  });

  it("returns nothing for an empty transcript", () => {
    expect(groupCues([])).toEqual([]);
  });

  it("merges sentences that are far too short to stand alone", () => {
    // Four short lines make one paragraph, not four rows.
    const cues = [cue(0, 4, 30), cue(4, 4, 30), cue(8, 4, 30), cue(12, 4, 30)];
    expect(groupCues(cues)).toEqual([{ start: 0, end: 16, from: 0, to: 3 }]);
  });

  it("starts a new block after a real pause in the speech", () => {
    const cues = [cue(0, 4, 30), cue(4, 4, 30), cue(20, 4, 30)];
    const blocks = groupCues(cues);
    expect(blocks.map((b) => [b.from, b.to])).toEqual([[0, 1], [2, 2]]);
  });

  it("closes a full block at the end of a sentence, not mid-sentence", () => {
    // The block closes at reading length and a sentence end.
    const cues = Array.from({ length: 8 }, (_, i) => cue(i * 3, 3, 60));
    expect(groupCues(cues).map((b) => [b.from, b.to])).toEqual([[0, 4], [5, 7]]);
  });

  it("does not break a sentence that runs across several cues", () => {
    // Without a sentence end the block cannot close.
    const cues = Array.from({ length: 6 }, (_, i) => cue(i * 3, 3, 60, i === 5));
    expect(groupCues(cues).map((b) => [b.from, b.to])).toEqual([[0, 5]]);
  });

  it("cuts a block that never ends a sentence rather than letting it grow forever", () => {
    // Without a hard ceiling a wall of text would appear.
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
    // With already paragraph-sized lines the grouping does nothing.
    const cues = [cue(0, 40, 300), cue(40, 40, 300), cue(80, 40, 300)];
    expect(groupCues(cues).map((b) => [b.from, b.to])).toEqual([[0, 0], [1, 1], [2, 2]]);
  });

  it("ends a sentence on a script that does not use the full stop", () => {
    // The CJK punctuation has to count as a sentence end too.
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

  // Verbatim what a real recogniser returned for 30 seconds.
  it("turns a real myLab transcript into coarse paragraphs", () => {
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
    // Two paragraphs, cut like the coarse provider does, only without a remainder.
    expect(groupCues(cues).map((b) => [b.from, b.to])).toEqual([[0, 4], [5, 8]]);
  });
});


// The answer sentence names two moments, only one was marked.


// The same case, the second line stood next to it unmarked.
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
  // Filler so the frequency filter recognises the common words.
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
    // Common words must not count, otherwise half the chunk hangs on the citation.
    expect(claimLineIndices(claim, spanne, korpus)).not.toContain(0);
  });

  it("ohne Sieger bleibt die Liste leer, der ganze Abschnitt wird markiert", () => {
    expect(claimLineIndices("Das ist so.", spanne, korpus)).toEqual([]);
  });

  it("ein kurzes Wort zieht keine Zeile herein, auch wenn es selten ist", () => {
    // A rare short word says nothing, that is what the length rule is for.
    const kurz = "In der Woche werden noch affine Schifren geübt.";
    expect(claimLineIndices(kurz, spanne, korpus)).toEqual([11]);
  });
});

describe("chooseableTargetLangs", () => {
  it("drops the language of the recording", () => {
    expect(chooseableTargetLangs(["de", "en", "fr"], "de")).toEqual(["en", "fr"]);
  });

  it("keeps every language while the recording language is unknown", () => {
    expect(chooseableTargetLangs(["de", "en"], null)).toEqual(["de", "en"]);
  });

  it("compares case-insensitively, the codes come from two sources", () => {
    expect(chooseableTargetLangs(["de", "en"], "DE")).toEqual(["en"]);
  });
});

describe("readPendingTranslation", () => {
  const jetzt = 1_000_000;

  it("returns the language while the note is still fresh", () => {
    const roh = JSON.stringify({ ts: jetzt - 1000, lang: "fr" });
    expect(readPendingTranslation(roh, jetzt)).toBe("fr");
  });

  it("returns null once the note is older than the timeout", () => {
    const roh = JSON.stringify({ ts: jetzt - 11 * 60 * 1000, lang: "fr" });
    expect(readPendingTranslation(roh, jetzt)).toBeNull();
  });

  it("returns null for a missing or unreadable note", () => {
    expect(readPendingTranslation(null, jetzt)).toBeNull();
    expect(readPendingTranslation("kaputt", jetzt)).toBeNull();
  });

  it("returns null for the old note that carried only a timestamp", () => {
    expect(readPendingTranslation(String(jetzt - 1000), jetzt)).toBeNull();
  });
});

describe("buildTranscriptOptions", () => {
  it("hangs the plus entry below the tracks", () => {
    expect(buildTranscriptOptions({ hasSource: true, hasTarget: false, canTranslate: true }))
      .toEqual(["source", "off", TRANSLATE_ACTION]);
  });

  it("leaves the list untouched when nobody may translate", () => {
    expect(buildTranscriptOptions({ hasSource: true, hasTarget: true, canTranslate: false }))
      .toEqual(["source", "target", "both", "off"]);
  });
});

describe("sentenceSpan — the mark follows the sentence, not the cue", () => {
  const cue = (text: string) => ({ text });

  it("keeps a cue that is a whole sentence to itself", () => {
    const list = [cue("Erster Satz."), cue("Zweiter Satz."), cue("Dritter Satz.")];
    expect(sentenceSpan(list, 1)).toEqual({
      fromIdx: 1, fromChar: 0, toIdx: 1, toChar: "Zweiter Satz.".length,
    });
  });

  it("reaches back into the cue before when the sentence starts there", () => {
    const prev = "Das ist ein Satz. Und der naechste faengt hier an";
    const list = [cue(prev), cue("und laeuft hier zu Ende.")];
    expect(sentenceSpan(list, 1)).toEqual({
      fromIdx: 0, fromChar: prev.indexOf("Und"), toIdx: 1, toChar: "und laeuft hier zu Ende.".length,
    });
  });

  it("reaches forward into the next cue when the sentence ends there", () => {
    const next = "und endet hier. Danach kommt mehr.";
    const list = [cue("Ein Satz laeuft hier los"), cue(next)];
    expect(sentenceSpan(list, 0)).toEqual({
      fromIdx: 0, fromChar: 0, toIdx: 1, toChar: next.indexOf(".") + 1,
    });
  });

  it("spans both sides at once", () => {
    const prev = "Ende hier. Ein Satz beginnt";
    const next = "und schliesst hier! Neuer Satz.";
    const list = [cue(prev), cue("laeuft weiter"), cue(next)];
    expect(sentenceSpan(list, 1)).toEqual({
      fromIdx: 0, fromChar: prev.indexOf("Ein"), toIdx: 2, toChar: next.indexOf("!") + 1,
    });
  });

  it("stops after a few cues when there is no punctuation at all", () => {
    const list = Array.from({ length: 20 }, () => cue("wort wort wort"));
    const span = sentenceSpan(list, 10);
    expect(span?.fromIdx).toBe(4);
    expect(span?.toIdx).toBe(16);
  });

  it("reads a sentence end outside the latin script too", () => {
    const prev = "前の文。次の文はここから";
    const list = [cue(prev), cue("ここで終わる。")];
    expect(sentenceSpan(list, 1)?.fromIdx).toBe(0);
    expect(sentenceSpan(list, 1)?.fromChar).toBe(prev.indexOf("次"));
  });

  it("has no span without a running cue", () => {
    expect(sentenceSpan([cue("Ein Satz.")], -1)).toBeNull();
  });
});

describe("translationProbeOutcome", () => {
  it("reports done once the file exists", () => {
    expect(translationProbeOutcome({ exists: true })).toEqual({ kind: "done" });
  });

  it("keeps waiting while nothing is there yet", () => {
    expect(translationProbeOutcome({ exists: false })).toEqual({ kind: "wait" });
  });

  it("reports the failure with the provider's message", () => {
    expect(translationProbeOutcome({ exists: false, error: "Internal Server Error" }))
      .toEqual({ kind: "failed", error: "Internal Server Error" });
  });

  it("treats an unreadable answer as still waiting", () => {
    expect(translationProbeOutcome(null)).toEqual({ kind: "wait" });
    expect(translationProbeOutcome("kaputt")).toEqual({ kind: "wait" });
  });
});
