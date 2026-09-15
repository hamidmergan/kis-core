import { describe, expect, it } from "vitest";
import { applyRegen } from "./apply";

const TEXT = "Die Spannung liegt an. Der Widerstand bremst.";

describe("applyRegen", () => {
  it("ersetzt den ganzen Text", () => {
    expect(applyRegen(TEXT, "liegt an", "replace-all", "Neu.")).toBe("Neu.");
  });

  it("ersetzt nur die markierte Stelle", () => {
    expect(applyRegen(TEXT, "liegt an", "replace-selection", "steht an"))
      .toBe("Die Spannung steht an. Der Widerstand bremst.");
  });

  it("setzt den Vorschlag vor die Markierung", () => {
    expect(applyRegen(TEXT, "Der Widerstand", "insert-before", "Kurz gesagt:"))
      .toBe("Die Spannung liegt an. Kurz gesagt: Der Widerstand bremst.");
  });

  it("setzt den Vorschlag hinter die Markierung", () => {
    expect(applyRegen(TEXT, "liegt an", "insert-after", "in Volt"))
      .toBe("Die Spannung liegt an in Volt. Der Widerstand bremst.");
  });

  it("ersetzt alles, wenn nichts markiert war", () => {
    expect(applyRegen(TEXT, "", "replace-selection", "Neu.")).toBe("Neu.");
  });

  it("laesst den Text stehen, wenn die Markierung nicht mehr vorkommt", () => {
    expect(applyRegen(TEXT, "gibt es nicht", "replace-selection", "Neu.")).toBe(TEXT);
  });
});
