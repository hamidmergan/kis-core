/** Empty, unchanged or really new, only the last case may save. */
import { describe, expect, it } from "vitest";

import { renameCommit, renameErrorText } from "./renameCommit";

describe("renameCommit", () => {
  it("speichert einen wirklich neuen Namen", () => {
    expect(renameCommit("Neuer Name", "Alter Name")).toEqual({
      kind: "save",
      title: "Neuer Name",
    });
  });

  it("trimmt vor dem Speichern", () => {
    expect(renameCommit("  Neuer Name  ", "Alter Name")).toEqual({
      kind: "save",
      title: "Neuer Name",
    });
  });

  it("bricht bei leerer Eingabe ab", () => {
    expect(renameCommit("", "Alter Name")).toEqual({ kind: "abort" });
  });

  it("bricht bei reinen Leerzeichen ab", () => {
    expect(renameCommit("   ", "Alter Name")).toEqual({ kind: "abort" });
  });

  it("bricht ab, wenn der Name unveraendert ist", () => {
    expect(renameCommit("Alter Name", "Alter Name")).toEqual({ kind: "abort" });
  });

  it("erkennt unveraendert auch mit Leerzeichen drumherum", () => {
    expect(renameCommit("  Alter Name  ", "Alter Name")).toEqual({ kind: "abort" });
  });
});

describe("renameErrorText", () => {
  it("nimmt den Grund vom Server", () => {
    expect(renameErrorText(new Error("Der Name darf nicht leer sein"), "Allgemein"))
      .toBe("Der Name darf nicht leer sein");
  });

  it("faellt ohne Grund auf den allgemeinen Satz zurueck", () => {
    expect(renameErrorText(new Error(""), "Allgemein")).toBe("Allgemein");
    expect(renameErrorText("kein Fehlerobjekt", "Allgemein")).toBe("Allgemein");
    expect(renameErrorText(undefined, "Allgemein")).toBe("Allgemein");
  });
});
