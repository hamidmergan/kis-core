import { describe, expect, it } from "vitest";
import { eventActive } from "@/lib/event/eventWindow";
import type { EventBlock } from "@/lib/event/types";

const EMPTY = { de: "", en: "" };
const block: EventBlock = { enabled: true, ignoreWindow: false, from: "2026-11-06", until: "2026-11-13", heading: EMPTY, text: EMPTY, tiles: [] };

describe("eventActive", () => {
  it("is off when switched off", () => {
    expect(eventActive({ ...block, enabled: false }, new Date("2026-11-10T12:00:00Z"))).toBe(false);
  });

  it("covers the whole last day", () => {
    expect(eventActive(block, new Date("2026-11-13T21:00:00Z"))).toBe(true);
    expect(eventActive(block, new Date("2026-11-14T12:00:00Z"))).toBe(false);
  });

  it("waits for the first day", () => {
    expect(eventActive(block, new Date("2026-11-05T12:00:00Z"))).toBe(false);
    expect(eventActive(block, new Date("2026-11-06T12:00:00Z"))).toBe(true);
  });

  it("treats empty bounds as open and honours ignoreWindow", () => {
    expect(eventActive({ ...block, from: "", until: "" }, new Date("2030-01-01T12:00:00Z"))).toBe(true);
    expect(eventActive({ ...block, ignoreWindow: true }, new Date("2030-01-01T12:00:00Z"))).toBe(true);
  });
});
