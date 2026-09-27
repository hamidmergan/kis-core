/** The number fields for simultaneous calls turn into the object the provider stores. */
import { describe, expect, it } from "vitest";

import { CONCURRENCY_BUCKETS, bucketsFor, buildConcurrency, concurrencyToFields } from "./_concurrency";

describe("bucketsFor", () => {
  it("zeigt fuer Chat und Bildanalyse nur das Feld LLM", () => {
    expect(bucketsFor(["chat", "vision"])).toEqual(["llm"]);
  });

  it("zeigt fuer reine Bildanalyse das Feld LLM", () => {
    expect(bucketsFor(["vision"])).toEqual(["llm"]);
  });

  it("fasst Bilder erzeugen und bearbeiten in einem Feld zusammen", () => {
    expect(bucketsFor(["image_edit", "image_gen"])).toEqual(["image"]);
  });

  it("haelt die feste Reihenfolge der Felder ein", () => {
    const alle = ["ocr", "embedding", "tts", "stt", "image_gen", "chat", "translation"];
    expect(bucketsFor(alle)).toEqual(["llm", "stt", "tts", "image", "embedding", "ocr"]);
  });

  it("zeigt fuer Uebersetzung allein kein Feld", () => {
    expect(bucketsFor(["translation"])).toEqual([]);
  });

  it("folgt der Reihenfolge aus den Metadaten", () => {
    expect(bucketsFor(["chat", "stt"], ["stt", "llm"])).toEqual(["stt", "llm"]);
  });

  it("kennt alle sechs Felder", () => {
    expect(CONCURRENCY_BUCKETS).toEqual(["llm", "stt", "tts", "image", "embedding", "ocr"]);
  });
});

describe("buildConcurrency", () => {
  it("uebernimmt eine gueltige Zahl", () => {
    expect(buildConcurrency({ llm: "10" }, ["llm"])).toEqual({ llm: 10 });
  });

  it("laesst ein leeres Feld weg", () => {
    expect(buildConcurrency({ llm: "10", stt: "" }, ["llm", "stt"])).toEqual({ llm: 10 });
  });

  it("schneidet Leerzeichen ab", () => {
    expect(buildConcurrency({ llm: " 4 " }, ["llm"])).toEqual({ llm: 4 });
  });

  it("laesst Null, Kommazahlen, Text und negative Werte weg", () => {
    const felder = { llm: "0", stt: "2.5", tts: "abc", image: "-3" };
    expect(buildConcurrency(felder, ["llm", "stt", "tts", "image"])).toEqual({});
  });

  it("laesst 1000 zu, aber nichts darueber", () => {
    expect(buildConcurrency({ llm: "1000", stt: "1001" }, ["llm", "stt"])).toEqual({ llm: 1000 });
  });

  it("laesst Felder weg, die gerade nicht angezeigt werden", () => {
    expect(buildConcurrency({ llm: "10", tts: "3" }, ["llm"])).toEqual({ llm: 10 });
  });
});

describe("concurrencyToFields", () => {
  it("macht aus den gespeicherten Zahlen Feldinhalte", () => {
    expect(concurrencyToFields({ llm: 10, ocr: 2 })).toEqual({ llm: "10", ocr: "2" });
  });

  it("gibt ohne gespeicherte Werte leere Felder", () => {
    expect(concurrencyToFields(undefined)).toEqual({});
  });
});
