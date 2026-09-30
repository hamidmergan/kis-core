import { describe, expect, it } from "vitest";
import {
  bildPlaetze, closedForGood, fortschrittMeldung, hasContent, isBusy, kannEinfuegen, reachable, rowCountOk, schrittFuer, skizzen,
  stepIndex,
} from "./_logic";
import { INITIAL_STATE, reducer } from "./_reducer";
import { STEPS, type Outline, type PraesentationState, type Slide } from "./_types";

const state = (over: Partial<PraesentationState> = {}): PraesentationState => ({ ...INITIAL_STATE, ...over });
const outline = (n: number): Outline => ({
  title: "D", subtitle: "", rows: Array.from({ length: n }, (_, i) => ({ id: `s${i + 1}`, role: "text", title: `T${i}`, gist: "" })),
});
const folie = (id: string, over: Partial<Slide> = {}): Slide =>
  ({ id, role: "text", layout: 1, title: id, subtitle: "", body: null, columns: [], images: [], notes: "", ...over });

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
  it("der Ablauf hat drei Schritte, die Vorschau zeigt Bau und Ergebnis zugleich", () => {
    expect([...STEPS]).toEqual(["content", "preview", "done"]);
  });
});

describe("reachable", () => {
  it("nichts ist erreichbar, solange etwas läuft", () => {
    const s = state({ step: "preview", maxReached: 2, jobStatus: "running", jobUuid: "x" });
    expect(reachable(stepIndex("done"), s)).toBe(false);
    expect(isBusy(s)).toBe(true);
  });
  it("der Inhalt ist nur ohne Auftrag erreichbar", () => {
    expect(reachable(0, state({ step: "preview", maxReached: 1, jobUuid: "x", jobStatus: "awaiting_user" }))).toBe(false);
    expect(reachable(0, state({ step: "preview", maxReached: 1 }))).toBe(true);
  });
  it("fertig ist nur nach Erfolg erreichbar", () => {
    const s = state({ step: "preview", maxReached: 2, jobUuid: "x", jobStatus: "awaiting_user" });
    expect(reachable(stepIndex("done"), s)).toBe(false);
    expect(reachable(stepIndex("done"), { ...s, jobStatus: "success" })).toBe(true);
  });
  it("die Vorschau bleibt vom Fertig-Schritt aus erreichbar", () => {
    const s = state({ step: "done", maxReached: 2, jobUuid: "x", jobStatus: "success", slides: [folie("s1")] });
    expect(reachable(stepIndex("preview"), s)).toBe(true);
    expect(closedForGood(stepIndex("preview"), s)).toBe(false);
  });
  it("die Vorschau braucht wenigstens die Gliederung", () => {
    const s = state({ step: "done", maxReached: 2, jobUuid: "x", jobStatus: "failed" });
    expect(reachable(stepIndex("preview"), s)).toBe(false);
    expect(reachable(stepIndex("preview"), { ...s, outline: outline(3) })).toBe(true);
  });
});

describe("schrittFuer", () => {
  it("Bau, Entwurf und Änderungen gehören in die Vorschau", () => {
    expect(schrittFuer("running", { step: "texte" })).toBe("preview");
    expect(schrittFuer("failed", { step: "bilder" })).toBe("preview");
    expect(schrittFuer("awaiting_user", null)).toBe("preview");
  });
  it("Fertigstellen und Erfolg landen in Fertig, eine spätere Änderung wieder in der Vorschau", () => {
    expect(schrittFuer("running", { step: "bau", final: true })).toBe("done");
    expect(schrittFuer("paused", { step: "bau", final: true })).toBe("done");
    expect(schrittFuer("success", { step: "done", final: true })).toBe("done");
    expect(schrittFuer("awaiting_user", { step: "done", final: true })).toBe("preview");
  });
});

describe("fortschrittMeldung", () => {
  it("ein frischer Start liest erst die Materialien", () => {
    expect(fortschrittMeldung("pending", null).key).toBe("progressMaterial");
  });
  it("Zähler nur, wenn es eine Gesamtzahl gibt", () => {
    expect(fortschrittMeldung("running", { step: "texte", current: 3, total: 12 }))
      .toEqual({ key: "progressTexts", values: { done: 3, total: 12 } });
    expect(fortschrittMeldung("pending", { step: "texte" }).key).toBe("progressTextsStart");
    expect(fortschrittMeldung("pending", { step: "bilder" }).key).toBe("progressImagesStart");
  });
  it("warten auf den Anbieter geht vor", () => {
    expect(fortschrittMeldung("waiting_retry", { step: "texte", current: 1, total: 4 }).key).toBe("waitingRetry");
  });
});

describe("skizzen", () => {
  it("folgt der Gliederung und füllt jede Zeile, sobald ihre Folie geschrieben ist", () => {
    const k = skizzen(outline(3), [folie("s2", { body: { kind: "bullets", items: ["a"] } as Slide["body"] })]);
    expect(k.map((x) => x.id)).toEqual(["s1", "s2", "s3"]);
    expect(k.map((x) => x.slide?.id ?? null)).toEqual([null, "s2", null]);
  });
  it("eine eingefügte Folie ohne Inhalt ist noch nicht geschrieben", () => {
    const k = skizzen(outline(2), [folie("s1"), folie("s2", { body: { kind: "bullets", items: ["a"] } as Slide["body"] })]);
    expect(k.map((x) => x.slide?.id ?? null)).toEqual([null, "s2"]);
    expect(skizzen(null, [folie("s1", { role: "abschnitt" })])[0].slide?.id).toBe("s1");
  });
  it("ohne Gliederung gibt es noch nichts zu skizzieren", () => {
    expect(skizzen(null, [])).toEqual([]);
  });
});

describe("bildPlaetze", () => {
  it("nummeriert die Bilder und hängt das Bild im Textfeld an", () => {
    const body = { kind: "image", prompt: "p" } as Slide["body"];
    expect(bildPlaetze(folie("s1", { images: [{ prompt: "a" }, { prompt: "b" }], body }))).toEqual(["0", "1", "body"]);
    expect(bildPlaetze(folie("s1"))).toEqual([]);
  });
});

describe("closedForGood", () => {
  it("der Inhalt ist mit dem Auftrag endgültig zu", () => {
    expect(closedForGood(stepIndex("content"), state({ step: "preview", maxReached: 1, jobUuid: "x" }))).toBe(true);
    expect(closedForGood(stepIndex("content"), state({ step: "content" }))).toBe(false);
  });
  it("Vorschau und Fertig bleiben offen", () => {
    const s = state({ step: "done", maxReached: 3, jobUuid: "x", jobStatus: "success" });
    expect(closedForGood(stepIndex("preview"), s)).toBe(false);
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
    const s = state({ step: "preview", jobUuid: "x", jobStatus: "running" });
    expect(reducer(s, { type: "JOB", status: "success", progress: { step: "done" } }).step).toBe("done");
  });
  it("der Start öffnet die Vorschau, ein fertiger Entwurf bleibt dort", () => {
    const s = reducer(state(), { type: "STARTING" });
    expect(s.step).toBe("preview");
    const n = reducer({ ...s, jobUuid: "x", jobStatus: "running" }, { type: "JOB", status: "awaiting_user", progress: null });
    expect(n.step).toBe("preview");
  });
  it("was eine Änderung neu macht, gilt nur, solange sie läuft", () => {
    const s = reducer(state({ step: "preview", jobUuid: "x", jobStatus: "pending" }), { type: "IN_ARBEIT", ids: ["s4"] });
    expect(reducer(s, { type: "JOB", status: "running", progress: { step: "bilder" } }).inArbeit).toEqual(["s4"]);
    expect(reducer(s, { type: "JOB", status: "awaiting_user", progress: null }).inArbeit).toEqual([]);
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
    const s = state({ missingImages: ["s1"], images: { s1: ["0"] }, hasDeck: true, templateFallback: true });
    const n = reducer(s, { type: "STARTING" });
    expect(n.missingImages).toEqual([]);
    expect(n.images).toEqual({});
    expect(n.hasDeck).toBe(false);
    expect(n.templateFallback).toBe(false);
  });
});

describe("VIEW bump", () => {
  it("bump erhöht jede erhaltene Version", () => {
    const s = state({ previews: { s1: 1, s2: 3 } });
    const n = reducer(s, { type: "VIEW", outline: null, slides: [], previews: ["s1", "s2"], missingImages: [],
                           images: {}, hasDeck: false, templateFallback: false, bump: true });
    expect(n.previews).toEqual({ s1: 2, s2: 4 });
  });
  it("ohne bump bleiben bestehende Versionen unverändert", () => {
    const s = state({ previews: { s1: 1, s2: 3 } });
    const n = reducer(s, { type: "VIEW", outline: null, slides: [], previews: ["s1", "s2"], missingImages: [],
                           images: {}, hasDeck: false, templateFallback: false });
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

describe("RESET und BACK_TO_START", () => {
  it("setzt ganz neu an, auch der Bildstil folgt wieder der Vorlage", () => {
    const n = reducer(state({ step: "done", jobUuid: "x", instructions: "nur Kapitel 2", imageStyle: "Aquarell" }), { type: "RESET" });
    expect(n.step).toBe("content");
    expect(n.jobUuid).toBeNull();
    expect(n.instructions).toBe("");
    expect(n.imageStyle).toBeNull();
  });
  it("wirft beim Abbruch vor der Gliederung nur den Auftrag weg, die Angaben bleiben", () => {
    const vorher = state({ step: "preview", jobUuid: "x", jobStatus: "running", maxReached: 1, instructions: "nur Kapitel 2", imageStyle: "Aquarell",
                           presenter: "Prof. Muster", language: "en", notes: true, templateId: "eigen",
                           source: { mode: "module", files: [], moduleId: "m1", sourceIds: ["q1"] } });
    const n = reducer(vorher, { type: "BACK_TO_START" });
    expect(n.step).toBe("content");
    expect(n.maxReached).toBe(0);
    expect(n.jobUuid).toBeNull();
    expect(n.jobStatus).toBe("idle");
    expect(n.instructions).toBe("nur Kapitel 2");
    expect(n.imageStyle).toBe("Aquarell");
    expect(n.presenter).toBe("Prof. Muster");
    expect(n.language).toBe("en");
    expect(n.notes).toBe(true);
    expect(n.templateId).toBe("eigen");
    expect(n.source.sourceIds).toEqual(["q1"]);
  });
});

describe("SET_TEMPLATE und Bildstil", () => {
  it("eine andere Vorlage bringt ihren eigenen Stil, dieselbe behaelt den geaenderten", () => {
    const geaendert = reducer(state(), { type: "SET_IMAGE_STYLE", text: "Aquarell" });
    expect(reducer(geaendert, { type: "SET_TEMPLATE", templateId: "thl" }).imageStyle).toBe("Aquarell");
    expect(reducer(geaendert, { type: "SET_TEMPLATE", templateId: "eigen" }).imageStyle).toBeNull();
  });
  it("Zuruecksetzen heisst wieder der Stil der Vorlage", () => {
    const geaendert = reducer(state(), { type: "SET_IMAGE_STYLE", text: "Aquarell" });
    expect(reducer(geaendert, { type: "SET_IMAGE_STYLE", text: null }).imageStyle).toBeNull();
  });
});
