import { describe, expect, it } from "vitest";
import { SEED_CONFIG } from "../../_lib/seed";
import { EMPTY_CARD, type MockupCard } from "../../_lib/types";
import {
  isComplete,
  openStations,
  resizeStations,
  stamp,
  stampedIds,
  suggestNext,
  syncCompletion,
} from "./stampLogic";

const stations = SEED_CONFIG.stations.slice(0, 3);
const ids = stations.map((s) => s.id);

describe("stamp", () => {
  it("adds a stamp and leaves a repeated or unknown stamp alone", () => {
    const once = stamp(EMPTY_CARD, stations, ids[1], 1000);
    expect(once.stamped).toEqual({ [ids[1]]: 1000 });
    expect(stamp(once, stations, ids[1], 2000)).toBe(once);
    expect(stamp(once, stations, "nope", 2000)).toBe(once);
    expect(once.completedAt).toBeNull();
  });

  it("works in any order and completes with the last open station", () => {
    let card = stamp(EMPTY_CARD, stations, ids[2], 1);
    card = stamp(card, stations, ids[0], 2);
    expect(isComplete(card, stations)).toBe(false);
    card = stamp(card, stations, ids[1], 3);
    expect(isComplete(card, stations)).toBe(true);
    expect(card.completedAt).toBe(3);
  });

  it("ignores orphaned stamps from removed stations", () => {
    const card: MockupCard = { ...EMPTY_CARD, stamped: { ghost: 1, [ids[0]]: 2 } };
    expect(stampedIds(card, stations)).toEqual([ids[0]]);
    expect(openStations(card, stations).map((s) => s.id)).toEqual([ids[1], ids[2]]);
    expect(isComplete(card, stations)).toBe(false);
  });
});

describe("suggestNext", () => {
  it("picks the next open station after the current one and wraps around", () => {
    const card = stamp(EMPTY_CARD, stations, ids[1], 1);
    expect(suggestNext(card, stations, ids[1])?.id).toBe(ids[2]);
    const later = stamp(card, stations, ids[2], 2);
    expect(suggestNext(later, stations, ids[2])?.id).toBe(ids[0]);
    expect(suggestNext(stamp(later, stations, ids[0], 3), stations, ids[0])).toBeNull();
  });

  it("starts at the first open station without a reference", () => {
    expect(suggestNext(EMPTY_CARD, stations)?.id).toBe(ids[0]);
    expect(suggestNext(EMPTY_CARD, [])).toBeNull();
  });
});

describe("syncCompletion", () => {
  it("sets the time when the station list shrinks to the stamped ones and clears it when it grows", () => {
    const card = stamp(stamp(EMPTY_CARD, stations, ids[0], 1), stations, ids[1], 2);
    const shrunk = syncCompletion(card, stations.slice(0, 2), 50);
    expect(shrunk.completedAt).toBe(50);
    expect(syncCompletion(shrunk, stations, 60).completedAt).toBeNull();
    expect(syncCompletion(card, stations, 70)).toBe(card);
  });
});

describe("resizeStations", () => {
  it("cuts, refills from the seed and then invents stands with unique ids", () => {
    expect(resizeStations(SEED_CONFIG.stations, 3).map((s) => s.id)).toEqual(SEED_CONFIG.stations.slice(0, 3).map((s) => s.id));
    const five = resizeStations(stations, 5);
    expect(five.map((s) => s.id)).toEqual([...SEED_CONFIG.stations.map((s) => s.id), "stand-1"]);
    const eight = resizeStations(SEED_CONFIG.stations, 8);
    expect(eight).toHaveLength(8);
    expect(new Set(eight.map((s) => s.id)).size).toBe(8);
    expect(resizeStations(eight, 9).map((s) => s.id)).toContain("stand-5");
  });
});
