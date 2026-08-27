/** Your own and the configuration account never get a delete button. */
import { describe, expect, it } from "vitest";

import { canDeleteUser } from "./canDeleteUser";

const ICH = { userId: 1, email: "admin@th-luebeck.de" };

describe("canDeleteUser", () => {
  it("bietet ein fremdes Konto zum Loeschen an", () => {
    expect(canDeleteUser({ id: 7, email: "studi@th-luebeck.de" }, ICH)).toBe(true);
  });

  it("bietet das eigene Konto nicht an", () => {
    expect(canDeleteUser({ id: 1, email: "admin@th-luebeck.de" }, ICH)).toBe(false);
  });

  it("erkennt das eigene Konto auch ohne Mailadresse", () => {
    expect(canDeleteUser({ id: 1, email: null }, ICH)).toBe(false);
  });

  it("erkennt das Konto aus der Konfiguration an der Mailadresse", () => {
    expect(canDeleteUser({ id: 42, email: "admin@th-luebeck.de" }, ICH)).toBe(false);
  });

  it("laesst sich von Grossschreibung nicht taeuschen", () => {
    expect(canDeleteUser({ id: 42, email: "Admin@TH-Luebeck.de" }, ICH)).toBe(false);
  });

  it("haelt zwei leere Mailadressen nicht fuer dieselbe Person", () => {
    expect(canDeleteUser({ id: 7, email: "" }, { userId: 1, email: "" })).toBe(true);
  });
});
