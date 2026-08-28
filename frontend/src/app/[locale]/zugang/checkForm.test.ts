import { describe, expect, it } from "vitest";
import { checkForm, MIN_PASSWORD_LENGTH } from "./checkForm";

const gueltig = {
  code: "4K2P-7RXM",
  givenName: "Max",
  surname: "Mustermann",
  password: "geheim123",
  repeat: "geheim123",
};

describe("checkForm", () => {
  it("laesst eine vollstaendige Eingabe durch", () => {
    expect(checkForm(gueltig)).toEqual({ ok: true });
  });

  it("verlangt einen Code", () => {
    expect(checkForm({ ...gueltig, code: "  " })).toEqual({ ok: false, reason: "codeMissing" });
  });

  it("verlangt beide Namen", () => {
    expect(checkForm({ ...gueltig, surname: "" })).toEqual({ ok: false, reason: "nameMissing" });
  });

  it("verlangt ein langes genug Passwort", () => {
    const kurz = "a".repeat(MIN_PASSWORD_LENGTH - 1);
    expect(checkForm({ ...gueltig, password: kurz, repeat: kurz })).toEqual({
      ok: false,
      reason: "tooShort",
    });
  });

  it("verlangt zwei gleiche Passwoerter", () => {
    expect(checkForm({ ...gueltig, repeat: "anders123" })).toEqual({
      ok: false,
      reason: "mismatch",
    });
  });
});
