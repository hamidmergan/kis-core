/** The seat count is split between a dropdown and a free number field. */
import { describe, expect, it } from "vitest";

import { choiceToSeats, seatsToChoice } from "./seats";

describe("seatsToChoice", () => {
  it("waehlt den passenden Listeneintrag", () => {
    expect(seatsToChoice(25)).toEqual({ choice: "25", custom: "" });
  });

  it("kennt den einzelnen Platz", () => {
    expect(seatsToChoice(1)).toEqual({ choice: "1", custom: "" });
  });

  it("faellt bei einer fremden Zahl auf das freie Feld zurueck", () => {
    expect(seatsToChoice(37)).toEqual({ choice: "custom", custom: "37" });
  });
});

describe("choiceToSeats", () => {
  it("liest die Zahl aus dem Listeneintrag", () => {
    expect(choiceToSeats("50", "")).toBe(50);
  });

  it("liest die Zahl aus dem freien Feld", () => {
    expect(choiceToSeats("custom", "37")).toBe(37);
  });

  it("meldet ein leeres freies Feld als unbrauchbar", () => {
    expect(choiceToSeats("custom", "")).toBeNull();
  });

  it("laesst keine Null zu", () => {
    expect(choiceToSeats("custom", "0")).toBeNull();
  });

  it("laesst nichts ueber der Obergrenze zu", () => {
    expect(choiceToSeats("custom", "501")).toBeNull();
  });

  it("laesst 500 Plaetze fuer eine grosse Veranstaltung zu", () => {
    expect(choiceToSeats("custom", "500")).toBe(500);
  });

  it("laesst keine Kommazahl zu", () => {
    expect(choiceToSeats("custom", "3.5")).toBeNull();
  });
});
