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
    const a = startAuswahl(3, null);
    expect(a.imScreencast).toEqual([0, 1, 2]);
    expect(a.neuVertonen).toEqual([]);
  });

  it("waehlt nichts vor, auch wenn Folien geaendert sind", () => {
    const a = startAuswahl(3, null);
    expect(a.neuVertonen).toEqual([]);
  });

  it("die gespeicherten Screencast-Folien gewinnen", () => {
    const a = startAuswahl(3, { video_folien: [0, 2], neu_vertonen: [2] });
    expect(a.imScreencast).toEqual([0, 2]);
  });

  it("ein gespeichertes neu_vertonen wird NICHT wiederhergestellt", () => {
    // Das gilt nur fuer einen Lauf, sonst haengt ein alter Stand ewig fest.
    const a = startAuswahl(3, { video_folien: [0, 1, 2], neu_vertonen: [0, 1, 2] });
    expect(a.imScreencast).toEqual([0, 1, 2]);
    expect(a.neuVertonen).toEqual([]);
  });

  it("eine Folie ohne Ton wird nicht automatisch angehakt", () => {
    const a = startAuswahl(3, { video_folien: [0, 1, 2], neu_vertonen: [] });
    expect(a.neuVertonen).toEqual([]);
  });

  it("nur Folien im Screencast koennen neu vertont werden", () => {
    const a = startAuswahl(3, { video_folien: [0], neu_vertonen: [2] });
    expect(a.neuVertonen).toEqual([]);
  });

  it("video_folien gleich null heisst alle", () => {
    const a = startAuswahl(3, { video_folien: null, neu_vertonen: [] });
    expect(a.imScreencast).toEqual([0, 1, 2]);
  });
});

describe("angleichen", () => {
  it("wirft Folien raus, die nicht mehr im Screencast sind", () => {
    expect(angleichen([0, 1], [1, 2])).toEqual([1]);
  });

  it("ergaenzt nichts, es filtert nur", () => {
    expect(angleichen([0, 1], [])).toEqual([]);
  });

  it("eine Folie ausserhalb des Screencasts bleibt draussen", () => {
    expect(angleichen([0], [1])).toEqual([]);
  });

  it("leerer Screencast leert auch die Vertonungs-Auswahl", () => {
    expect(angleichen([], [0, 1])).toEqual([]);
  });

  it("die Nummern kommen aufsteigend zurueck", () => {
    expect(angleichen([0, 1, 2], [2, 0])).toEqual([0, 2]);
  });
});
