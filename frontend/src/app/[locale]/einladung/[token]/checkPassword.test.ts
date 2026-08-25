/**
 * Wann der Knopf auf der Einladungsseite ueberhaupt etwas abschickt.
 *
 * Das Backend prueft dasselbe noch einmal. Hier geht es darum, dass die Person
 * den Grund sieht, bevor sie klickt, statt eine Fehlermeldung zurueckzubekommen.
 */
import { describe, expect, it } from "vitest";

import { checkPassword, MIN_PASSWORD_LENGTH } from "./checkPassword";

describe("checkPassword", () => {
  it("laesst ein langes Passwort durch, das zweimal gleich ist", () => {
    expect(checkPassword("ein-langes-passwort", "ein-langes-passwort")).toEqual({ ok: true });
  });

  it("haelt ein zu kurzes Passwort auf", () => {
    expect(checkPassword("kurz", "kurz")).toEqual({ ok: false, reason: "tooShort" });
  });

  it("haelt zwei verschiedene Eingaben auf", () => {
    expect(checkPassword("ein-langes-passwort", "ein-anderes-passwort")).toEqual({
      ok: false,
      reason: "mismatch",
    });
  });

  it("meldet die Laenge zuerst, damit nicht beides gleichzeitig blinkt", () => {
    expect(checkPassword("kurz", "andere")).toEqual({ ok: false, reason: "tooShort" });
  });

  it("verlangt mindestens acht Zeichen, wie das Backend", () => {
    expect(MIN_PASSWORD_LENGTH).toBe(8);
  });

  it("laesst genau acht Zeichen durch und sieben nicht", () => {
    expect(checkPassword("12345678", "12345678")).toEqual({ ok: true });
    expect(checkPassword("1234567", "1234567")).toEqual({ ok: false, reason: "tooShort" });
  });
});
