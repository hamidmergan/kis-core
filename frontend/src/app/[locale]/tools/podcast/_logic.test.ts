import { describe, expect, it } from "vitest";
import { FAIL_AT, hasContent, linesToVoice, nextTick, reachable, rephrase } from "./_logic";
import { INITIAL_STATE, reducer } from "./_reducer";
import { sampleScript } from "./_samples";
import type { Line, Person, Run } from "./_types";

const line = (i: number, voiced = false): Line => ({ id: `l${i}`, speaker: i % 2, text: `Satz ${i}.`, audioOf: voiced ? `Satz ${i}.` : null });
const run = (over: Partial<Run> = {}): Run => ({ status: "running", failedId: null, failedOnce: false, voicedThisRun: 0, keptIds: [], cancelled: false, ...over });
const persons = (roles: Person["role"][]): Person[] => roles.map((role, i) => ({ name: `P${i + 1}`, role, voiceId: "" }));

describe("Welche Beiträge vertont werden", () => {
  it("nimmt nur die ohne Ton oder mit geändertem Text", () => {
    const lines = [line(0, true), { ...line(1, true), text: "Neu." }, line(2)];
    expect(linesToVoice(lines).map((l) => l.id)).toEqual(["l1", "l2"]);
  });

  it("vertont der Reihe nach, einen Beitrag je Tick", () => {
    const tick = nextTick([line(0), line(1)], run());
    expect(tick.kind).toBe("voiced");
    if (tick.kind === "voiced") expect(tick.lines.map((l) => l.audioOf)).toEqual(["Satz 0.", null]);
  });

  it("fällt im ersten Lauf genau einmal hin und behält das Fertige", () => {
    let lines = Array.from({ length: 10 }, (_, i) => line(i));
    let r = run();
    for (let i = 0; i < FAIL_AT; i++) {
      const tick = nextTick(lines, r);
      if (tick.kind === "voiced") lines = tick.lines;
      r = { ...r, voicedThisRun: r.voicedThisRun + 1 };
    }
    const fail = nextTick(lines, r);
    expect(fail).toEqual({ kind: "fail", id: "l4" });
    expect(linesToVoice(lines)).toHaveLength(10 - FAIL_AT);
    const resumed = nextTick(lines, { ...r, failedOnce: true });
    expect(resumed.kind).toBe("voiced");
  });

  it("meldet fertig, wenn nichts mehr offen ist", () => {
    expect(nextTick([line(0, true)], run())).toEqual({ kind: "done" });
  });
});

describe("Der Ablauf im Reducer", () => {
  it("merkt sich beim Start, was schon Ton hatte, und meldet den Fehler mit Beitrag", () => {
    const lines = [line(0, true), ...Array.from({ length: 8 }, (_, i) => line(i + 1))];
    let state = reducer({ ...INITIAL_STATE, lines, step: "script", maxReached: 2 }, { type: "START_VOICING" });
    expect(state.run.keptIds).toEqual(["l0"]);
    for (let i = 0; i < FAIL_AT + 1; i++) state = reducer(state, { type: "TICK" });
    expect(state.run.status).toBe("failed");
    expect(state.run.failedId).toBe("l5");
    state = reducer(state, { type: "RESUME" });
    for (let i = 0; i < 10; i++) state = reducer(state, { type: "TICK" });
    expect(state.run.status).toBe("done");
    expect(state.step).toBe("done");
    expect(linesToVoice(state.lines)).toHaveLength(0);
  });

  it("vertont nach einer Änderung nur den geänderten Beitrag", () => {
    const lines = [line(0, true), line(1, true), line(2, true)];
    let state = reducer({ ...INITIAL_STATE, lines, step: "done", maxReached: 4, run: run({ status: "done", failedOnce: true }) }, { type: "UPDATE_LINE", id: "l1", text: "Anders." });
    expect(linesToVoice(state.lines).map((l) => l.id)).toEqual(["l1"]);
    state = reducer(state, { type: "START_VOICING" });
    expect(state.run.keptIds).toEqual(["l0", "l2"]);
    state = reducer(state, { type: "TICK" });
    state = reducer(state, { type: "TICK" });
    expect(state.run.status).toBe("done");
  });

  it("lässt beim Abbruch das Vertonte stehen", () => {
    let state = reducer({ ...INITIAL_STATE, lines: [line(0, true), line(1)], step: "script", maxReached: 2 }, { type: "START_VOICING" });
    state = reducer(state, { type: "CANCEL" });
    expect(state.step).toBe("script");
    expect(state.run.cancelled).toBe(true);
    expect(state.lines[0].audioOf).toBe("Satz 0.");
  });
});

describe("Was in der Fortschrittsleiste anklickbar ist", () => {
  it("sperrt Vertonung und Fertig, bis es sie gibt", () => {
    const state = { ...INITIAL_STATE, step: "script" as const, maxReached: 2 };
    expect(reachable(0, state)).toBe(true);
    expect(reachable(3, state)).toBe(false);
    expect(reachable(4, state)).toBe(false);
  });

  it("sperrt alles, solange die Vertonung läuft", () => {
    const state = { ...INITIAL_STATE, step: "voicing" as const, maxReached: 3, run: run() };
    expect(reachable(2, state)).toBe(false);
  });

  it("öffnet Fertig erst nach dem Lauf, das Skript aber nach einem Fehler", () => {
    const failed = { ...INITIAL_STATE, step: "voicing" as const, maxReached: 3, run: run({ status: "failed" }) };
    expect(reachable(2, failed)).toBe(true);
    expect(reachable(4, failed)).toBe(false);
    const done = { ...failed, step: "script" as const, maxReached: 4, run: run({ status: "done" }) };
    expect(reachable(4, done)).toBe(true);
  });
});

describe("Das Beispielskript", () => {
  it("verteilt die Beiträge nach Rollen und setzt die Namen ein", () => {
    const lines = sampleScript("de", persons(["host", "expert"]));
    expect(new Set(lines.map((l) => l.speaker))).toEqual(new Set([0, 1]));
    expect(lines[0].text).toContain("P2");
  });

  it("lässt bei einer Person einen Vortrag entstehen", () => {
    const lines = sampleScript("de", persons(["host"]));
    expect(lines.every((l) => l.speaker === 0)).toBe(true);
  });

  it("nimmt bei vier Personen alle vier Rollen mit", () => {
    const lines = sampleScript("en", persons(["host", "expert", "student", "critic"]));
    expect(new Set(lines.map((l) => l.speaker)).size).toBe(4);
  });
});

describe("Kleine Helfer", () => {
  it("stellt beim Umformulieren den letzten Satz nach vorn", () => {
    expect(rephrase("Eins. Zwei. Drei.")).toBe("Drei. Eins. Zwei.");
    expect(rephrase("Nur einer.")).toBe("Nur einer.");
  });

  it("kennt Inhalt je nach Quelle", () => {
    expect(hasContent({ mode: "text", text: "  ", files: [], moduleId: "", sourceIds: [] })).toBe(false);
    expect(hasContent({ mode: "files", text: "", files: ["a.pdf"], moduleId: "", sourceIds: [] })).toBe(true);
    expect(hasContent({ mode: "module", text: "", files: [], moduleId: "et1", sourceIds: [] })).toBe(false);
  });
});
