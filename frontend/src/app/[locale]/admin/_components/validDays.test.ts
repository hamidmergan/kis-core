/** The code lifetime is split between a dropdown and a free day field. */
import { describe, expect, it } from "vitest";

import { choiceToDays, daysToChoice, remainingDays } from "./validDays";

describe("daysToChoice", () => {
  it("waehlt den passenden Listeneintrag", () => {
    expect(daysToChoice(14)).toEqual({ choice: "14", custom: "" });
  });

  it("faellt bei einer fremden Zahl auf das freie Feld zurueck", () => {
    expect(daysToChoice(3)).toEqual({ choice: "custom", custom: "3" });
  });
});

describe("choiceToDays", () => {
  it("liest die Zahl aus dem Listeneintrag", () => {
    expect(choiceToDays("30", "")).toBe(30);
  });

  it("liest die Zahl aus dem freien Feld", () => {
    expect(choiceToDays("custom", "90")).toBe(90);
  });

  it("meldet leer, null und zu gross als unbrauchbar", () => {
    expect(choiceToDays("custom", "")).toBeNull();
    expect(choiceToDays("custom", "0")).toBeNull();
    expect(choiceToDays("custom", "366")).toBeNull();
    expect(choiceToDays("custom", "2.5")).toBeNull();
  });
});

describe("remainingDays", () => {
  const jetzt = new Date("2026-10-07T12:00:00Z").getTime();

  it("rundet angebrochene Tage auf", () => {
    expect(remainingDays("2026-10-09T13:00:00Z", jetzt)).toBe(3);
  });

  it("bleibt bei einem abgelaufenen Code bei einem Tag", () => {
    expect(remainingDays("2026-10-01T12:00:00Z", jetzt)).toBe(1);
  });
});
