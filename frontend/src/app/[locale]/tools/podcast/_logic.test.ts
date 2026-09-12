import { describe, expect, it } from "vitest";
import { failedLineIndex, hasContent, isBusy, linesToVoice, minutesOf, needsVoice, reachable, wordsOf } from "./_logic";
import { INITIAL_STATE, reducer } from "./_reducer";
import type { Line, PodcastState } from "./_types";

const line = (n: number, text = `Satz ${n}.`): Line => ({ id: `b${n}`, speaker: n % 2, text });
const state = (over: Partial<PodcastState> = {}): PodcastState => ({ ...INITIAL_STATE, ...over });

describe("Welche Beiträge noch vertont werden müssen", () => {
  it("nimmt die, für die der Server keinen Ton meldet", () => {
    const lines = [line(0), line(1), line(2)];
    expect(linesToVoice(lines, ["b0", "b2"]).map((l) => l.id)).toEqual(["b1"]);
    expect(needsVoice(lines[0], ["b0"])).toBe(false);
  });

  it("zählt beim ersten Lauf alle", () => {
    expect(linesToVoice([line(0), line(1)], [])).toHaveLength(2);
  });
});

describe("Eine Änderung am Beitrag", () => {
  it("nimmt genau diesem Beitrag den Ton, den anderen nicht", () => {
    const vorher = state({ lines: [line(0), line(1)], voicedIds: ["b0", "b1"] });
    const nachher = reducer(vorher, { type: "UPDATE_LINE", id: "b1", text: "Anders." });
    expect(nachher.voicedIds).toEqual(["b0"]);
    expect(linesToVoice(nachher.lines, nachher.voicedIds).map((l) => l.id)).toEqual(["b1"]);
  });

  it("räumt beim Löschen auch den Ton weg", () => {
    const nachher = reducer(state({ lines: [line(0), line(1)], voicedIds: ["b0", "b1"] }),
                            { type: "DELETE_LINE", id: "b0" });
    expect(nachher.lines.map((l) => l.id)).toEqual(["b1"]);
    expect(nachher.voicedIds).toEqual(["b1"]);
  });

  it("hängt einen neuen Beitrag ohne Ton an und wechselt die Person", () => {
    const nachher = reducer(state({ lines: [line(0)], count: 2, voicedIds: ["b0"] }), { type: "ADD_LINE" });
    expect(nachher.lines).toHaveLength(2);
    expect(nachher.lines[1].speaker).toBe(1);
    expect(needsVoice(nachher.lines[1], nachher.voicedIds)).toBe(true);
  });
});

describe("Der Auftrag treibt den Ablauf", () => {
  it("räumt beim Start das alte Skript weg und geht zum Skript-Schritt", () => {
    const nachher = reducer(state({ lines: [line(0)], voicedIds: ["b0"], error: "alt" }), { type: "STARTING" });
    expect(nachher.step).toBe("script");
    expect(nachher.lines).toEqual([]);
    expect(nachher.voicedIds).toEqual([]);
    expect(nachher.error).toBe("");
    expect(isBusy(nachher)).toBe(true);
  });

  it("springt bei Erfolg auf Fertig", () => {
    const nachher = reducer(state({ step: "voicing", jobUuid: "x" }),
                            { type: "JOB", status: "success", progress: { step: "done" } });
    expect(nachher.step).toBe("done");
  });

  it("bleibt beim Fehler stehen und merkt sich die Meldung", () => {
    const nachher = reducer(state({ step: "voicing" }), { type: "FAIL", error: "Beitrag 5 ging nicht" });
    expect(nachher.step).toBe("voicing");
    expect(nachher.jobStatus).toBe("failed");
    expect(failedLineIndex(nachher.error)).toBe(4);
  });

  it("liest aus einer Meldung ohne Zahl keinen Beitrag", () => {
    expect(failedLineIndex("Die Vertonung ist fehlgeschlagen.")).toBe(-1);
  });
});

describe("Was in der Fortschrittsleiste anklickbar ist", () => {
  it("sperrt alles, solange der Auftrag arbeitet", () => {
    const laufend = state({ step: "voicing", maxReached: 3, jobStatus: "running", jobUuid: "x" });
    expect(reachable(2, laufend)).toBe(false);
  });

  it("schließt Inhalt und Besetzung, sobald ein Auftrag läuft", () => {
    const mitAuftrag = state({ step: "script", maxReached: 2, jobUuid: "x", jobStatus: "awaiting_user" });
    expect(reachable(0, mitAuftrag)).toBe(false);
    expect(reachable(1, mitAuftrag)).toBe(false);
    const ohne = state({ step: "cast", maxReached: 1 });
    expect(reachable(0, ohne)).toBe(true);
  });

  it("öffnet Fertig erst nach dem Lauf und die Vertonung erst mit Ton", () => {
    const offen = state({ step: "script", maxReached: 2, jobUuid: "x", jobStatus: "awaiting_user" });
    expect(reachable(3, offen)).toBe(false);
    expect(reachable(4, offen)).toBe(false);
    const fertig = state({ step: "script", maxReached: 4, jobUuid: "x", jobStatus: "success",
                           progress: { fertig: [0, 1] } });
    expect(reachable(3, fertig)).toBe(true);
    expect(reachable(4, fertig)).toBe(true);
  });

  it("lässt nach einem Fehler zurück in die Vertonung", () => {
    const kaputt = state({ step: "script", maxReached: 3, jobUuid: "x", jobStatus: "failed" });
    expect(reachable(3, kaputt)).toBe(true);
  });
});

describe("Kleine Helfer", () => {
  it("kennt Inhalt je nach Quelle", () => {
    expect(hasContent({ mode: "text", text: "  ", files: [], moduleId: "", sourceIds: [] })).toBe(false);
    expect(hasContent({ mode: "text", text: "Etwas", files: [], moduleId: "", sourceIds: [] })).toBe(true);
    expect(hasContent({ mode: "module", text: "", files: [], moduleId: "m1", sourceIds: [] })).toBe(false);
    expect(hasContent({ mode: "module", text: "", files: [], moduleId: "m1", sourceIds: ["s1"] })).toBe(true);
  });

  it("schätzt die Länge aus den Wörtern, mindestens eine Minute", () => {
    expect(wordsOf([line(0, "eins zwei drei")])).toBe(3);
    expect(minutesOf([line(0, "eins zwei drei")])).toBe(1);
    expect(minutesOf([line(0, Array(700).fill("wort").join(" "))])).toBe(5);
  });
});
