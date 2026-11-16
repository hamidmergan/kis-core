import { describe, expect, it } from "vitest";
import type { ScheduleListEntry } from "./ScheduleEntryCardGlobal";
import { monthGrid, rangesOn } from "./_monthGrid";

let nextId = 1;
const entry = (due: string, extra: Partial<ScheduleListEntry> = {}): ScheduleListEntry => ({
  id: nextId++,
  workspace_uuid: "ws-a",
  module_title: "Kurs A",
  module_relation: "enrolled",
  title: "Termin",
  due_date: due,
  ...extra,
});

describe("monthGrid", () => {
  it("lays out October 2026, which starts on a Thursday and needs five weeks", () => {
    const g = monthGrid([], 2026, 9, new Set());
    expect(g).toMatchObject({ daysInMonth: 31, daysInPrev: 30, startCol: 3, weeks: 5 });
  });

  it("sorts single days, month-only entries and spans into their places", () => {
    const tag = entry("2026-10-05");
    const monat = entry("2026-10-01", { date_precision: "month" });
    const spanne = entry("2026-09-28", { end_date: "2026-10-02" });
    const gleicherTag = entry("2026-10-07", { end_date: "2026-10-07" });
    const anderswo = entry("2026-11-01");
    const g = monthGrid([tag, monat, spanne, gleicherTag, anderswo], 2026, 9, new Set());
    expect([...g.byDay.keys()]).toEqual(["2026-10-05", "2026-10-07"]);
    expect(g.noDay).toEqual([monat]);
    expect(g.monthRanges).toEqual([spanne]);
    expect(rangesOn(g.monthRanges, "2026-10-02")).toEqual([spanne]);
    expect(rangesOn(g.monthRanges, "2026-10-03")).toEqual([]);
  });

  it("keeps a hidden workspace in the legend but out of the grid", () => {
    const a = entry("2026-10-05");
    const privat = entry("2026-10-06", { workspace_uuid: null, module_title: null, module_relation: "personal" });
    const g = monthGrid([privat, a], 2026, 9, new Set(["ws-a"]));
    expect(g.groups).toEqual([{ key: "ws-a", title: "Kurs A" }, { key: "privat", title: null }]);
    expect([...g.byDay.keys()]).toEqual(["2026-10-06"]);
  });
});
