import { describe, expect, it } from "vitest";
import { laneCount, weekSegments, type RangeEntry } from "./_ranges";

const klausurphase: RangeEntry = {
  id: 1, title: "Klausurphase", due_date: "2027-02-15", end_date: "2027-02-26", color: "#0F766E",
};
const abgabefenster: RangeEntry = {
  id: 2, title: "Abgabefenster", due_date: "2027-02-22", end_date: "2027-03-05", color: "#9D174D",
};

describe("weekSegments", () => {
  it("gibt nichts zurueck, wenn die Woche den Zeitraum nicht beruehrt", () => {
    expect(weekSegments([klausurphase], "2027-02-01")).toEqual([]);
  });

  it("schneidet am rechten Wochenrand ab und merkt sich die Fortsetzung", () => {
    const [s] = weekSegments([klausurphase], "2027-02-15");
    expect(s.col1).toBe(1);
    expect(s.col2).toBe(8);
    expect(s.openLeft).toBe(false);
    expect(s.openRight).toBe(true);
  });

  it("schneidet am linken Wochenrand ab", () => {
    const [s] = weekSegments([klausurphase], "2027-02-22");
    expect(s.col1).toBe(1);
    expect(s.col2).toBe(6);
    expect(s.openLeft).toBe(true);
    expect(s.openRight).toBe(false);
  });

  it("faengt mitten in der Woche an", () => {
    const mittwochs: RangeEntry = { ...klausurphase, id: 5, due_date: "2027-02-17", end_date: "2027-02-19" };
    const [s] = weekSegments([mittwochs], "2027-02-15");
    expect(s.col1).toBe(3);
    expect(s.col2).toBe(6);
    expect(s.openLeft).toBe(false);
    expect(s.openRight).toBe(false);
  });

  it("stapelt zwei Zeitraeume in derselben Woche", () => {
    const segmente = weekSegments([klausurphase, abgabefenster], "2027-02-22");
    expect(segmente).toHaveLength(2);
    expect(segmente[0].lane).toBe(0);
    expect(segmente[1].lane).toBe(1);
  });

  it("legt zwei Zeitraeume ohne Ueberschneidung auf dieselbe Spur", () => {
    const frueh: RangeEntry = { ...klausurphase, id: 3, due_date: "2027-02-22", end_date: "2027-02-23" };
    const spaet: RangeEntry = { ...abgabefenster, id: 4, due_date: "2027-02-26", end_date: "2027-02-28" };
    const segmente = weekSegments([frueh, spaet], "2027-02-22");
    expect(segmente.map((s) => s.lane)).toEqual([0, 0]);
  });

  it("kommt mit einem Wochenanfang im Vormonat zurecht", () => {
    // Das April-Raster faengt am Montag, dem 29. Maerz an.
    const ueberDenMonat: RangeEntry = { ...abgabefenster, id: 6, due_date: "2027-03-30", end_date: "2027-04-02" };
    const [s] = weekSegments([ueberDenMonat], "2027-03-29");
    expect(s.col1).toBe(2);
    expect(s.col2).toBe(6);
    expect(s.openLeft).toBe(false);
    expect(s.openRight).toBe(false);
  });
});

describe("laneCount", () => {
  it("zaehlt die belegten Spuren", () => {
    expect(laneCount(weekSegments([klausurphase, abgabefenster], "2027-02-22"))).toBe(2);
    expect(laneCount([])).toBe(0);
  });
});
