import { describe, expect, it } from "vitest";
import { gruppiere } from "./_gruppen";
import type { CampusChatEintrag } from "./_types";

function chat(id: number, updated: string): CampusChatEintrag {
  return { id, title: `Chat ${id}`, question_count: 1, created_at: updated, updated_at: updated };
}

describe("gruppiere", () => {
  // The backend sends UTC without a Z, 2026-10-04 14:00 local is 12:00 UTC.
  const jetzt = new Date("2026-10-04T14:00:00+02:00");

  it("legt heute, die letzten sieben Tage und älter auseinander", () => {
    const out = gruppiere(
      [chat(1, "2026-10-04T09:00:00"), chat(2, "2026-10-03T20:00:00"), chat(3, "2026-09-28T08:00:00"), chat(4, "2026-09-20T08:00:00")],
      jetzt,
    );
    expect(out.heute.map((c) => c.id)).toEqual([1]);
    expect(out.woche.map((c) => c.id)).toEqual([2, 3]);
    expect(out.aelter.map((c) => c.id)).toEqual([4]);
  });

  it("hält die Reihenfolge der Liste", () => {
    const out = gruppiere([chat(5, "2026-10-04T10:00:00"), chat(6, "2026-10-04T11:00:00")], jetzt);
    expect(out.heute.map((c) => c.id)).toEqual([5, 6]);
  });

  it("bleibt bei leerer Liste leer", () => {
    expect(gruppiere([], jetzt)).toEqual({ heute: [], woche: [], aelter: [] });
  });
});
