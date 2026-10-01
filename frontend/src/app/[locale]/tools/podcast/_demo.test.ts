import { describe, expect, it } from "vitest";
import { demoSkript, demoVertonung } from "./_demo";
import type { Line } from "./_types";

const zeilen = (n: number): Line[] => Array.from({ length: n }, (_, i) => ({ id: `b${i}`, speaker: i % 2, text: `T${i}` }));

describe("demoSkript", () => {
  it("schreibt Teil für Teil, jeder fertige Teil ist sofort lesbar", () => {
    const momente = demoSkript(zeilen(10));
    expect(momente.map((m) => m.progress)).toEqual([
      { step: "script", part: 1, total: 2 },
      { step: "script", part: 2, total: 2 },
    ]);
    expect(momente.map((m) => m.draft.length)).toEqual([7, 10]);
  });
});

describe("demoVertonung", () => {
  it("vertont Beitrag für Beitrag und setzt dann zusammen", () => {
    const momente = demoVertonung(zeilen(3));
    expect(momente.map((m) => m.progress)).toEqual([
      { step: "tts", fertig: [0] },
      { step: "tts", fertig: [0, 1] },
      { step: "tts", fertig: [0, 1, 2] },
      { step: "montage" },
    ]);
  });
});
