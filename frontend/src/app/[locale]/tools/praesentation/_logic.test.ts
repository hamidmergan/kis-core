import { describe, expect, it } from "vitest";
import { closedForGood, hasContent, isBusy, kannEinfuegen, reachable, rowCountOk, stepIndex } from "./_logic";
import { INITIAL_STATE, reducer } from "./_reducer";
import { STEPS, type Outline, type PraesentationState } from "./_types";

const state = (over: Partial<PraesentationState> = {}): PraesentationState => ({ ...INITIAL_STATE, ...over });
const outline = (n: number): Outline => ({
  title: "D", subtitle: "", rows: Array.from({ length: n }, (_, i) => ({ id: `s${i + 1}`, role: "text", title: `T${i}`, gist: "" })),
});

describe("rowCountOk", () => {
  it("erlaubt drei bis 30 Folien", () => {
    expect(rowCountOk(outline(3))).toBe(true);
    expect(rowCountOk(outline(17))).toBe(true);
    expect(rowCountOk(outline(30))).toBe(true);
    expect(rowCountOk(outline(2))).toBe(false);
    expect(rowCountOk(outline(31))).toBe(false);
  });
  it("lässt die Untergrenze fallen, sobald Folien da sind", () => {
    expect(rowCountOk(outline(2), true)).toBe(true);
    expect(rowCountOk(outline(30), true)).toBe(true);
    expect(rowCountOk(outline(31), true)).toBe(false);
    expect(rowCountOk(outline(0), true)).toBe(false);
  });
});

describe("STEPS", () => {
  it("der Ablauf hat drei Schritte, die Gliederung ist keiner davon", () => {
    expect([...STEPS]).toEqual(["content", "slides", "done"]);
  });
});

describe("reachable", () => {
  it("nichts ist erreichbar, solange etwas läuft", () => {
    const s = state({ step: "slides", maxReached: 2, jobStatus: "running", jobUuid: "x" });
    expect(reachable(stepIndex("done"), s)).toBe(false);
    expect(isBusy(s)).toBe(true);
  });
  it("der Inhalt ist nur ohne Auftrag erreichbar", () => {
    expect(reachable(0, state({ step: "slides", maxReached: 1, jobUuid: "x", jobStatus: "awaiting_user" }))).toBe(false);
    expect(reachable(0, state({ step: "slides", maxReached: 1 }))).toBe(true);
  });
  it("fertig ist nur nach Erfolg erreichbar", () => {
    const s = state({ step: "slides", maxReached: 2, jobUuid: "x", jobStatus: "awaiting_user" });
    expect(reachable(stepIndex("done"), s)).toBe(false);
    expect(reachable(stepIndex("done"), { ...s, jobStatus: "success" })).toBe(true);
  });
  it("die Folien bleiben vom Fertig-Schritt aus erreichbar", () => {
    const s = state({ step: "done", maxReached: 2, jobUuid: "x", jobStatus: "success", slides: [{ id: "s1" } as never] });
    expect(reachable(stepIndex("slides"), s)).toBe(true);
    expect(closedForGood(stepIndex("slides"), s)).toBe(false);
  });
});

describe("closedForGood", () => {
  it("der Inhalt ist mit dem Auftrag endgültig zu", () => {
    expect(closedForGood(stepIndex("content"), state({ step: "slides", maxReached: 1, jobUuid: "x" }))).toBe(true);
    expect(closedForGood(stepIndex("content"), state({ step: "content" }))).toBe(false);
  });
  it("Folien und Fertig bleiben offen", () => {
    const s = state({ step: "done", maxReached: 2, jobUuid: "x", jobStatus: "success" });
    expect(closedForGood(stepIndex("slides"), s)).toBe(false);
    expect(closedForGood(stepIndex("done"), s)).toBe(false);
  });
});

describe("hasContent", () => {
  it("Dateien oder Quellen eines Workspace", () => {
    expect(hasContent({ mode: "files", files: [], moduleId: "", sourceIds: [] })).toBe(false);
    expect(hasContent({ mode: "module", files: [], moduleId: "m", sourceIds: ["q"] })).toBe(true);
  });
});

describe("reducer", () => {
  it("eine Änderung an einer Folie erhöht ihren Vorschau-Zähler nicht, erst der Server", () => {
    const s = state({ slides: [{ id: "s1", role: "text", layout: 1, title: "A", subtitle: "", body: null, columns: [], images: [], notes: "" }],
                      previews: { s1: 1 } });
    const n = reducer(s, { type: "UPDATE_SLIDE", slide: { ...s.slides[0], title: "B" } });
    expect(n.slides[0].title).toBe("B");
    expect(n.previews.s1).toBe(1);
    expect(reducer(n, { type: "PREVIEW_FRESH", id: "s1" }).previews.s1).toBe(2);
  });
  it("Zeilen der Gliederung lassen sich verschieben und löschen", () => {
    const s = state({ outline: outline(3) });
    const bewegt = reducer(s, { type: "MOVE_ROW", id: "s3", delta: -1 });
    expect(bewegt.outline?.rows.map((r) => r.id)).toEqual(["s1", "s3", "s2"]);
    const weniger = reducer(bewegt, { type: "DELETE_ROW", id: "s3" });
    expect(weniger.outline?.rows.map((r) => r.id)).toEqual(["s1", "s2"]);
  });
  it("Erfolg wechselt nach fertig", () => {
    const s = state({ step: "slides", jobUuid: "x", jobStatus: "running" });
    expect(reducer(s, { type: "JOB", status: "success", progress: { step: "done" } }).step).toBe("done");
  });
  it("ein erfolgreicher Neustart löscht die alte Fehlermeldung", () => {
    // A stale error must clear once the resumed job is running again, but survive a failed or paused status without its own text.
    const nachFehler = reducer(state(), { type: "FAIL", error: "Kaputt" });
    const laeuft = reducer(nachFehler, { type: "JOB", status: "running", progress: null });
    expect(laeuft.error).toBe("");
    const erneutFehlgeschlagen = reducer(nachFehler, { type: "JOB", status: "failed", progress: null });
    expect(erneutFehlgeschlagen.error).toBe("Kaputt");
  });
  it("STARTING setzt Bildlücken, Deckflag und Vorlagen-Rückfall zurück", () => {
    const s = state({ missingImages: ["s1"], hasDeck: true, templateFallback: true });
    const n = reducer(s, { type: "STARTING" });
    expect(n.missingImages).toEqual([]);
    expect(n.hasDeck).toBe(false);
    expect(n.templateFallback).toBe(false);
  });
});

describe("VIEW bump", () => {
  it("bump erhöht jede erhaltene Version", () => {
    const s = state({ previews: { s1: 1, s2: 3 } });
    const n = reducer(s, { type: "VIEW", outline: null, slides: [], previews: ["s1", "s2"], missingImages: [],
                           hasDeck: false, templateFallback: false, bump: true });
    expect(n.previews).toEqual({ s1: 2, s2: 4 });
  });
  it("ohne bump bleiben bestehende Versionen unverändert", () => {
    const s = state({ previews: { s1: 1, s2: 3 } });
    const n = reducer(s, { type: "VIEW", outline: null, slides: [], previews: ["s1", "s2"], missingImages: [],
                           hasDeck: false, templateFallback: false });
    expect(n.previews).toEqual({ s1: 1, s2: 3 });
  });
});

describe("kannEinfuegen", () => {
  it("nimmt einen Titel allein", () => {
    expect(kannEinfuegen("Kühlung", "")).toBe(true);
  });
  it("nimmt eine Anweisung allein", () => {
    expect(kannEinfuegen("", "vergleiche die beiden Verfahren")).toBe(true);
  });
  it("lehnt zwei leere Felder ab, Leerzeichen zählen nicht", () => {
    expect(kannEinfuegen("", "")).toBe(false);
    expect(kannEinfuegen("  ", "  ")).toBe(false);
  });
});

describe("SET_NOTES_INCLUDE", () => {
  it("merkt sich den Schalter aus dem Folienschritt", () => {
    expect(INITIAL_STATE.notesInclude).toBe(true);
    const aus = reducer(state(), { type: "SET_NOTES_INCLUDE", include: false });
    expect(aus.notesInclude).toBe(false);
    expect(reducer(aus, { type: "SET_NOTES_INCLUDE", include: true }).notesInclude).toBe(true);
  });
});
