/** Spans in the timeline, due on the last day and with a year across the year boundary. */

import { describe, expect, it } from "vitest";
import {
  cleanScheduleDescription,
  effectiveDueDate,
  formatRangeEnd,
  urgencyColor,
  URGENCY_SOON,
} from "./utils";

describe("effectiveDueDate", () => {
  it("nimmt bei einer Spanne den letzten Tag", () => {
    expect(effectiveDueDate({ due_date: "2026-09-28", end_date: "2027-01-21" }))
      .toBe("2027-01-21");
  });

  it("nimmt ohne Spanne den einzigen Tag", () => {
    expect(effectiveDueDate({ due_date: "2027-01-03", end_date: null })).toBe("2027-01-03");
  });

  it("bleibt leer, wenn gar kein Datum dasteht", () => {
    expect(effectiveDueDate({ due_date: null })).toBeNull();
  });
});

describe("Dringlichkeit haengt am Ende, nicht am Anfang", () => {
  it("eine laufende Spanne ist nicht dringend, nur weil sie begonnen hat", () => {
    const eintrag = { due_date: "2026-09-28", end_date: "2027-01-21" };
    expect(urgencyColor(effectiveDueDate(eintrag), "2026-09-29")).toBeNull();
  });

  it("kurz vor dem Ende wird sie dringend", () => {
    const eintrag = { due_date: "2026-09-28", end_date: "2027-01-21" };
    expect(urgencyColor(effectiveDueDate(eintrag), "2027-01-18")).toBe(URGENCY_SOON);
  });
});

describe("formatRangeEnd", () => {
  it("nennt Tag und Monat, solange die Spanne im Jahr bleibt", () => {
    expect(formatRangeEnd("2026-09-28", "2026-11-02", "de")).toBe("2. November");
  });

  it("nennt das Jahr, sobald die Spanne es wechselt", () => {
    expect(formatRangeEnd("2026-09-28", "2027-01-21", "de")).toBe("21. Januar 2027");
  });

  it("kann Englisch", () => {
    expect(formatRangeEnd("2026-09-28", "2026-11-02", "en")).toBe("November 2");
  });

  it("gibt nichts zurueck, wenn es keine Spanne ist", () => {
    expect(formatRangeEnd("2026-09-28", null, "de")).toBeNull();
    expect(formatRangeEnd("2026-09-28", undefined, "de")).toBeNull();
    expect(formatRangeEnd(null, "2026-11-02", "de")).toBeNull();
  });

  it("ein Ende am selben Tag ist keine Spanne", () => {
    expect(formatRangeEnd("2026-09-28", "2026-09-28", "de")).toBeNull();
  });
});

describe("Der eigene Tag faellt aus der Beschreibung", () => {
  const clean = (text: string, datum: string | null = "2026-09-27") =>
    cleanScheduleDescription(text, null, datum);

  it("wirft 'bis <eigener Tag>' ganz raus", () => {
    expect(clean("bis 27.09.2026")).toBeNull();
  });

  it("wirft auch 'ab <eigener Tag>' raus", () => {
    expect(clean("ab 27.09.2026")).toBeNull();
  });

  it("kennt die Form ohne fuehrende Null und mit zweistelligem Jahr", () => {
    expect(clean("bis 27.9.2026")).toBeNull();
    expect(clean("bis 27.09.26")).toBeNull();
    expect(clean("bis zum 27.09.2026")).toBeNull();
  });

  it("laesst den Rest des Satzes stehen", () => {
    expect(clean("Belegung über das QIS-System, bis 27.09.2026"))
      .toBe("Belegung über das QIS-System");
  });

  it("ruehrt ein ANDERES Datum nicht an", () => {
    expect(clean("bis 02.11.2026")).toBe("bis 02.11.2026");
  });

  it("laesst alles stehen, wenn der Eintrag keinen Tag hat", () => {
    expect(clean("bis 27.09.2026", null)).toBe("bis 27.09.2026");
  });
});
