import { describe, expect, it } from "vitest";
import {
  CHAR_WARN_AT,
  ENDING_SOON_MS,
  MAX_RECORDING_MS,
  SESSION_CHAR_LIMIT,
  charState,
  countChars,
  recordingPhase,
} from "./_limits";

const said = (...texts: string[]) => texts.map((original) => ({ original, translation: "x".repeat(500) }));

describe("Dauer einer Aufnahme", () => {
  it("lässt eine frische Aufnahme einfach laufen", () => {
    expect(recordingPhase(0)).toBe("running");
    expect(recordingPhase(ENDING_SOON_MS - 1)).toBe("running");
  });

  it("warnt kurz vor der Kappe", () => {
    expect(recordingPhase(ENDING_SOON_MS)).toBe("endingSoon");
    expect(recordingPhase(MAX_RECORDING_MS - 1)).toBe("endingSoon");
  });

  it("stoppt an der Kappe", () => {
    expect(recordingPhase(MAX_RECORDING_MS)).toBe("stop");
    expect(recordingPhase(MAX_RECORDING_MS * 2)).toBe("stop");
  });
});

describe("Zeichen eines Gesprächs", () => {
  it("zählt beide Seiten zusammen, die Übersetzung aber nicht", () => {
    expect(countChars(said("Hallo", "Guten Tag"))).toBe(14);
  });

  it("zählt ein leeres Gespräch als null", () => {
    expect(countChars([])).toBe(0);
  });

  it("meldet freie Fahrt unter der Warnschwelle", () => {
    expect(charState(0)).toBe("ok");
    expect(charState(CHAR_WARN_AT - 1)).toBe("ok");
  });

  it("warnt ab der Warnschwelle", () => {
    expect(charState(CHAR_WARN_AT)).toBe("near");
    expect(charState(SESSION_CHAR_LIMIT - 1)).toBe("near");
  });

  it("ist an der Grenze voll", () => {
    expect(charState(SESSION_CHAR_LIMIT)).toBe("full");
    expect(charState(SESSION_CHAR_LIMIT + 5000)).toBe("full");
  });
});
