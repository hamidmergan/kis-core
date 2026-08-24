import { describe, expect, it } from "vitest";
import { renderProgress, geaenderteFolien, markeFuerFolie, laufWaereUmsonst, nichtsWirdGesprochen, stimmwechselOhneWirkung, type VertonterStand, type LaufStand } from "./_utils";
import type { JobStatus } from "@/lib/api";
import type { SlideData } from "@/types";

const status = (progress: unknown) => ({ progress } as unknown as JobStatus);

describe("renderProgress", () => {
  it("reicht die fertigen Folien durch", () => {
    expect(renderProgress(status({ step: "tts", current: 2, total: 5, fertig: [0, 3] })))
      .toEqual({ kind: "tts", current: 2, total: 5, fertig: [0, 3], nichtDabei: [] });
  });

  it("ein alter Job ohne Liste liefert eine leere Liste", () => {
    expect(renderProgress(status({ step: "tts", current: 2, total: 5 })))
      .toEqual({ kind: "tts", current: 2, total: 5, fertig: [], nichtDabei: [] });
  });

  it("reicht die ausgeschlossenen Folien durch", () => {
    expect(renderProgress(status({ step: "tts", current: 1, total: 2, fertig: [0], nicht_dabei: [1] })))
      .toEqual({ kind: "tts", current: 1, total: 2, fertig: [0], nichtDabei: [1] });
  });

  it("ein alter Job ohne nicht_dabei liefert eine leere Liste", () => {
    expect(renderProgress(status({ step: "tts", current: 2, total: 5, fertig: [0, 3] })))
      .toEqual({ kind: "tts", current: 2, total: 5, fertig: [0, 3], nichtDabei: [] });
  });

  it("andere Schritte bleiben unveraendert", () => {
    expect(renderProgress(status({ step: "concat" }))).toEqual({ kind: "concat" });
  });
});

const stand: VertonterStand = {
  scripts: ["Skript eins", "Skript zwei"],
  folientexte: ["Folie eins", "Folie zwei"],
  voice_id: "de-anna",
  provider_id: 2,
  target_lang: "EN-US",
};

describe("markeFuerFolie", () => {
  it("unveraendert ergibt keine Marke", () => {
    expect(markeFuerFolie(stand, 0, "Skript eins", "Folie eins")).toBe(null);
  });

  it("geaendertes Skript ergibt skript", () => {
    expect(markeFuerFolie(stand, 0, "Skript neu", "Folie eins")).toBe("skript");
  });

  it("geaenderter Folientext ergibt folie", () => {
    expect(markeFuerFolie(stand, 0, "Skript eins", "Folie neu")).toBe("folie");
  });

  it("beides geaendert nennt das Skript, das betrifft den Nutzer", () => {
    expect(markeFuerFolie(stand, 0, "Skript neu", "Folie neu")).toBe("skript");
  });

  it("Leerzeichen am Rand sind keine Aenderung", () => {
    expect(markeFuerFolie(stand, 0, "  Skript eins  ", "Folie eins\n")).toBe(null);
  });

  it("ohne Abzug gilt nichts als geaendert", () => {
    expect(markeFuerFolie(null, 0, "irgendwas", "anders")).toBe(null);
  });

  it("eine Folie hinter dem Abzug gilt als geaendert", () => {
    expect(markeFuerFolie(stand, 5, "Skript", "Folie")).toBe("skript");
  });
});

describe("geaenderteFolien", () => {
  const slides = (paare: [string, string][]): SlideData[] =>
    paare.map(([script, extractedText], index) => ({
      index, imageBase64: "", extractedText, script,
    }));

  it("liefert die Nummern der geaenderten Folien", () => {
    const s = slides([["Skript eins", "Folie eins"], ["Skript neu", "Folie zwei"]]);
    expect(geaenderteFolien(stand, s)).toEqual([1]);
  });

  it("ohne Abzug ist die Liste leer", () => {
    const s = slides([["a", "b"]]);
    expect(geaenderteFolien(null, s)).toEqual([]);
  });

  it("eine Folie ohne Skript zaehlt nicht, sie hat nichts zu sprechen", () => {
    const s = slides([["Skript eins", "Folie eins"], ["   ", "Folie neu"]]);
    expect(geaenderteFolien(stand, s)).toEqual([]);
  });
});

const standMitAllenFeldern: VertonterStand = {
  scripts: ["Skript eins", "Skript zwei"],
  folientexte: ["Folie eins", "Folie zwei"],
  voice_id: "de-anna",
  provider_id: 2,
  target_lang: "EN-US",
  speed: 0.9,
  slide_pause: 1.0,
  subtitles: false,
  video_folien: [0, 1],
};

const basis: LaufStand = {
  stand: standMitAllenFeldern,
  hatVideo: true,
  imScreencast: [0, 1],
  neuVertonen: [],
  ohneTon: [],
  geaendert: [],
  providerId: 2,
  voiceId: "de-anna",
  targetLang: "EN-US",
  speed: 0.9,
  slidePause: 1.0,
  subtitles: false,
};

describe("laufWaereUmsonst", () => {
  it("ohne Abzug ist der Lauf nie umsonst", () => {
    expect(laufWaereUmsonst({ ...basis, stand: null })).toBe(false);
  });

  it("ohne fertiges Video ist der Lauf nie umsonst", () => {
    expect(laufWaereUmsonst({ ...basis, hatVideo: false })).toBe(false);
  });

  it("alles gleich und nichts angehakt: der Lauf waere umsonst", () => {
    expect(laufWaereUmsonst(basis)).toBe(true);
  });

  it("eine angehakte Folie macht den Lauf sinnvoll", () => {
    expect(laufWaereUmsonst({ ...basis, neuVertonen: [0] })).toBe(false);
  });

  it("eine geaenderte Folie macht den Lauf sinnvoll", () => {
    expect(laufWaereUmsonst({ ...basis, geaendert: [1] })).toBe(false);
  });

  it("eine Folie ohne Ton im Screencast macht den Lauf sinnvoll", () => {
    expect(laufWaereUmsonst({ ...basis, ohneTon: [1] })).toBe(false);
  });

  it("eine Folie ohne Ton ausserhalb des Screencasts aendert nichts, der Lauf bliebe umsonst", () => {
    expect(laufWaereUmsonst({ ...basis, ohneTon: [2] })).toBe(true);
  });

  it("eine geaenderte Stimme macht den Lauf sinnvoll", () => {
    expect(laufWaereUmsonst({ ...basis, voiceId: "de-other" })).toBe(false);
  });

  it("ein geaenderter Anbieter macht den Lauf sinnvoll", () => {
    expect(laufWaereUmsonst({ ...basis, providerId: 3 })).toBe(false);
  });

  it("eine geaenderte Zielsprache macht den Lauf sinnvoll", () => {
    expect(laufWaereUmsonst({ ...basis, targetLang: "DE" })).toBe(false);
  });

  it("ein geaendertes Tempo macht den Lauf sinnvoll", () => {
    expect(laufWaereUmsonst({ ...basis, speed: 1.1 })).toBe(false);
  });

  it("eine geaenderte Folienpause macht den Lauf sinnvoll", () => {
    expect(laufWaereUmsonst({ ...basis, slidePause: 2.0 })).toBe(false);
  });

  it("geaenderte Untertitel machen den Lauf sinnvoll", () => {
    expect(laufWaereUmsonst({ ...basis, subtitles: true })).toBe(false);
  });

  it("eine andere Folienauswahl macht den Lauf sinnvoll", () => {
    expect(laufWaereUmsonst({ ...basis, imScreencast: [0] })).toBe(false);
  });

  it("ein alter Abzug ohne die vier neuen Felder kippt nicht, er gilt bei sonst gleichen Werten als umsonst", () => {
    const standOhneNeueFelder: VertonterStand = {
      scripts: ["Skript eins", "Skript zwei"],
      folientexte: ["Folie eins", "Folie zwei"],
      voice_id: "de-anna",
      provider_id: 2,
      target_lang: "EN-US",
    };
    expect(laufWaereUmsonst({ ...basis, stand: standOhneNeueFelder })).toBe(true);
  });
});

describe("nichtsWirdGesprochen", () => {
  it("keine Folie angehakt und keine ohne Ton: nichts wird gesprochen", () => {
    expect(nichtsWirdGesprochen(basis)).toBe(true);
  });

  it("eine angehakte Folie: es wird gesprochen", () => {
    expect(nichtsWirdGesprochen({ ...basis, neuVertonen: [0] })).toBe(false);
  });

  it("eine Folie ohne Ton im Screencast: es wird gesprochen", () => {
    expect(nichtsWirdGesprochen({ ...basis, ohneTon: [1] })).toBe(false);
  });

  it("eine Folie ohne Ton ausserhalb des Screencasts: es wird nicht gesprochen", () => {
    expect(nichtsWirdGesprochen({ ...basis, ohneTon: [2] })).toBe(true);
  });
});

describe("stimmwechselOhneWirkung", () => {
  it("Stimme gewechselt, nichts angehakt: wahr", () => {
    expect(stimmwechselOhneWirkung({ ...basis, voiceId: "de-other" })).toBe(true);
  });

  it("Anbieter gewechselt, nichts angehakt: wahr", () => {
    expect(stimmwechselOhneWirkung({ ...basis, providerId: 3 })).toBe(true);
  });

  it("Sprache gewechselt, nichts angehakt: wahr", () => {
    expect(stimmwechselOhneWirkung({ ...basis, targetLang: "DE" })).toBe(true);
  });

  it("Stimme gewechselt, aber eine Folie angehakt: falsch, der Wechsel wirkt", () => {
    expect(stimmwechselOhneWirkung({ ...basis, voiceId: "de-other", neuVertonen: [0] })).toBe(false);
  });

  it("Stimme gewechselt, aber eine Folie ohne Ton im Screencast: falsch, die bekaeme die neue Stimme", () => {
    expect(stimmwechselOhneWirkung({ ...basis, voiceId: "de-other", ohneTon: [1] })).toBe(false);
  });

  it("nichts gewechselt: falsch", () => {
    expect(stimmwechselOhneWirkung(basis)).toBe(false);
  });

  it("ohne Abzug: falsch", () => {
    expect(stimmwechselOhneWirkung({ ...basis, stand: null, voiceId: "de-other" })).toBe(false);
  });

  it("ohne fertiges Video: falsch", () => {
    expect(stimmwechselOhneWirkung({ ...basis, hatVideo: false, voiceId: "de-other" })).toBe(false);
  });
});
