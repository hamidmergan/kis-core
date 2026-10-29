import { describe, expect, it } from "vitest";
import { closedForGood, failedLineIndex, hasContent, hatErgebnisse, isBusy, linesToVoice, minutesOf, needsVoice, ohneKi, reachable, wordsOf } from "./_logic";
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

  it("nimmt den Ton, wenn der Beitrag eine andere Person bekommt", () => {
    const vorher = state({ lines: [line(0), line(1)], voicedIds: ["b0", "b1"], count: 3 });
    const nachher = reducer(vorher, { type: "SET_SPEAKER", id: "b1", speaker: 2 });
    expect(nachher.lines.find((l) => l.id === "b1")?.speaker).toBe(2);
    expect(nachher.voicedIds).toEqual(["b0"]);
  });

  it("lässt eine Person außerhalb der Besetzung nicht zu", () => {
    const vorher = state({ lines: [line(0)], voicedIds: ["b0"], count: 2 });
    const nachher = reducer(vorher, { type: "SET_SPEAKER", id: "b0", speaker: 3 });
    expect(nachher.lines[0].speaker).toBe(0);
    expect(nachher.voicedIds).toEqual(["b0"]);
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

  it("lässt den Inhalt nie anklicken", () => {
    expect(reachable(0, state({ step: "script", maxReached: 2, jobUuid: "x", jobStatus: "awaiting_user" }))).toBe(false);
    expect(reachable(0, state({ step: "cast", maxReached: 1 }))).toBe(false);
    expect(reachable(0, state({ step: "done", maxReached: 4, jobUuid: "x", jobStatus: "success" }))).toBe(false);
  });

  it("lässt zurück in die Besetzung, auch mit fertigem Podcast", () => {
    const wartend = state({ step: "script", maxReached: 2, jobUuid: "x", jobStatus: "awaiting_user" });
    expect(reachable(1, wartend)).toBe(true);
    const fertig = state({ step: "done", maxReached: 4, jobUuid: "x", jobStatus: "success",
                           progress: { fertig: [0, 1] } });
    expect(reachable(1, fertig)).toBe(true);
    const laufend = state({ step: "voicing", maxReached: 3, jobUuid: "x", jobStatus: "running" });
    expect(reachable(1, laufend)).toBe(false);
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
    expect(hasContent({ mode: "files", files: [], moduleId: "", sourceIds: [] })).toBe(false);
    // The empty path needs no material, the script is written by hand.
    expect(hasContent({ mode: "blank", files: [], moduleId: "", sourceIds: [] })).toBe(true);
    expect(hasContent({ mode: "module", files: [], moduleId: "m1", sourceIds: [] })).toBe(false);
    expect(hasContent({ mode: "module", files: [], moduleId: "m1", sourceIds: ["s1"] })).toBe(true);
  });

  it("kennt den Weg ohne KI vor und nach dem Start", () => {
    expect(ohneKi(state({}))).toBe(false);
    expect(ohneKi(state({ source: { mode: "blank", files: [], moduleId: "", sourceIds: [] } }))).toBe(true);
    // Back from the job list the path only remains in the settings.
    expect(ohneKi(state({ selfWritten: true }))).toBe(true);
  });

  it("schätzt die Länge aus den Wörtern, mindestens eine Minute", () => {
    expect(wordsOf([line(0, "eins zwei drei")])).toBe(3);
    expect(minutesOf([line(0, "eins zwei drei")])).toBe(1);
    expect(minutesOf([line(0, Array(700).fill("wort").join(" "))])).toBe(5);
  });
});

describe("Wann ein neuer Podcast nachfragen muss", () => {
  it("fragt nicht, solange es kein Skript gibt", () => {
    expect(hatErgebnisse(state())).toBe(false);
    expect(hatErgebnisse(state({ step: "cast", maxReached: 1 }))).toBe(false);
  });

  it("fragt nicht, solange der Auftrag das Skript noch schreibt", () => {
    expect(hatErgebnisse(state({ step: "script", jobUuid: "x", jobStatus: "running", lines: [] }))).toBe(false);
  });

  it("fragt, sobald das Skript da ist", () => {
    expect(hatErgebnisse(state({ step: "script", jobUuid: "x", lines: [line(0)] }))).toBe(true);
  });

  it("fragt auch beim fertigen Podcast", () => {
    expect(hatErgebnisse(state({ step: "done", jobUuid: "x", jobStatus: "success",
                                 lines: [line(0)], voicedIds: ["b0"] }))).toBe(true);
  });
});

