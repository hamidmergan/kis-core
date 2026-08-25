/**
 * Der Link, den die Verwaltung kopiert und selbst verschickt.
 *
 * Er entsteht im Browser aus der Adresse der Seite, damit lokal, auf dem
 * Testserver und in Betrieb jeweils der richtige Rechnername darin steht.
 */
import { describe, expect, it } from "vitest";

import { inviteUrl } from "./inviteUrl";

describe("inviteUrl", () => {
  it("haengt den Schluessel an die Einladungsseite", () => {
    expect(inviteUrl("https://kis.th-luebeck.de", "7Kq2xR")).toBe(
      "https://kis.th-luebeck.de/einladung/7Kq2xR",
    );
  });

  it("erzeugt keinen doppelten Schraegstrich", () => {
    expect(inviteUrl("http://localhost:3000/", "7Kq2xR")).toBe(
      "http://localhost:3000/einladung/7Kq2xR",
    );
  });
});
