import { describe, expect, it } from "vitest";
import { angleichen, ohneTonAberMitSkript, startAuswahl } from "./_auswahl";

const skripte = ["a", "b", "c"];

describe("ohneTonAberMitSkript", () => {
  it("nennt Folien mit Skript und ohne Ton", () => {
    expect(ohneTonAberMitSkript(skripte, [true, false, true])).toEqual([1]);
  });

  it("eine Folie ohne Skript zaehlt nicht", () => {
    expect(ohneTonAberMitSkript(["a", "  ", "c"], [true, false, false])).toEqual([2]);
  });

  it("ohne Ton-Liste ist nichts zu ergaenzen", () => {
    expect(ohneTonAberMitSkript(skripte, [])).toEqual([]);
  });
});

describe("startAuswahl", () => {
  it("ohne gespeicherte Auswahl sind alle Folien dabei", () => {
    const a = startAuswahl(3, null, [], [], skripte);
    expect(a.imScreencast).toEqual([0, 1, 2]);
    expect(a.neuVertonen).toEqual([]);
  });

  it("geaenderte Folien sind vorausgewaehlt", () => {
    const a = startAuswahl(3, null, [1], [true, true, true], skripte);
    expect(a.neuVertonen).toEqual([1]);
  });

  it("gespeicherte Auswahl gewinnt", () => {
    const a = startAuswahl(3, { video_folien: [0, 2], neu_vertonen: [2] }, [1], [true, true, true], skripte);
    expect(a.imScreencast).toEqual([0, 2]);
    expect(a.neuVertonen).toEqual([2]);
  });

  it("Folien ohne Ton kommen immer dazu", () => {
    const a = startAuswahl(3, { video_folien: [0, 1, 2], neu_vertonen: [] }, [], [true, false, true], skripte);
    expect(a.neuVertonen).toEqual([1]);
  });

  it("nur Folien im Screencast koennen neu vertont werden", () => {
    const a = startAuswahl(3, { video_folien: [0], neu_vertonen: [2] }, [], [true, true, true], skripte);
    expect(a.neuVertonen).toEqual([]);
  });

  it("video_folien gleich null heisst alle", () => {
    const a = startAuswahl(3, { video_folien: null, neu_vertonen: [] }, [], [true, true, true], skripte);
    expect(a.imScreencast).toEqual([0, 1, 2]);
  });
});

describe("angleichen", () => {
  it("wirft Folien raus, die nicht mehr im Screencast sind", () => {
    expect(angleichen([0, 1], [1, 2], new Set())).toEqual([1]);
  });

  it("nimmt eine gesperrte Folie beim Wiederhinzufuegen zurueck auf", () => {
    expect(angleichen([0, 1], [], new Set([1]))).toEqual([1]);
  });

  it("eine gesperrte Folie ausserhalb des Screencasts bleibt draussen", () => {
    expect(angleichen([0], [], new Set([1]))).toEqual([]);
  });

  it("leerer Screencast leert auch die Vertonungs-Auswahl", () => {
    expect(angleichen([], [0, 1], new Set([0]))).toEqual([]);
  });

  it("die Nummern kommen aufsteigend zurueck", () => {
    expect(angleichen([0, 1, 2], [2, 0], new Set([1]))).toEqual([0, 1, 2]);
  });
});
