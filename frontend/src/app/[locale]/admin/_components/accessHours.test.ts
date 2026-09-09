/** The account lifetime is split between a dropdown (presets + unbegrenzt) and a free hours field. */
import { describe, expect, it } from "vitest";

import { choiceToHours, hoursToChoice } from "./accessHours";

describe("hoursToChoice", () => {
  it("waehlt den passenden Listeneintrag", () => {
    expect(hoursToChoice(168)).toEqual({ choice: "168", custom: "" });
  });

  it("kennt die zwoelf Stunden fuer eine Veranstaltung", () => {
    expect(hoursToChoice(12)).toEqual({ choice: "12", custom: "" });
  });

  it("erkennt unbegrenzt an null", () => {
    expect(hoursToChoice(null)).toEqual({ choice: "unlimited", custom: "" });
  });

  it("faellt bei einer fremden Zahl auf das freie Feld zurueck", () => {
    expect(hoursToChoice(48)).toEqual({ choice: "custom", custom: "48" });
  });
});

describe("choiceToHours", () => {
  it("liest die Zahl aus dem Listeneintrag", () => {
    expect(choiceToHours("168", "")).toBe(168);
  });

  it("liest die Zahl aus dem freien Feld", () => {
    expect(choiceToHours("custom", "48")).toBe(48);
  });

  it("liest unbegrenzt als null", () => {
    expect(choiceToHours("unlimited", "")).toBeNull();
  });

  it("meldet ein leeres freies Feld als unbrauchbar", () => {
    expect(choiceToHours("custom", "")).toBeUndefined();
  });

  it("laesst keine Null zu", () => {
    expect(choiceToHours("custom", "0")).toBeUndefined();
  });

  it("laesst nichts ueber der Obergrenze zu", () => {
    expect(choiceToHours("custom", "721")).toBeUndefined();
  });

  it("laesst die Obergrenze selbst zu", () => {
    expect(choiceToHours("custom", "720")).toBe(720);
  });

  it("laesst keine Kommazahl zu", () => {
    expect(choiceToHours("custom", "3.5")).toBeUndefined();
  });
});
