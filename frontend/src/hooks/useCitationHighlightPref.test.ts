import { describe, it, expect } from "vitest";
import { readCitationHighlightPref } from "./useCitationHighlightPref";

// The citation highlight is ON by default; a stored "0" turns it off. Any other
// stored value (incl. legacy "1") keeps it on. Mirrors the persistence contract
// of useHildePref so behaviour is predictable across the two display prefs.
describe("readCitationHighlightPref", () => {
  it("defaults to enabled when nothing is stored", () => {
    expect(readCitationHighlightPref(null)).toBe(true);
  });

  it("is disabled when stored value is '0'", () => {
    expect(readCitationHighlightPref("0")).toBe(false);
  });

  it("is enabled when stored value is '1'", () => {
    expect(readCitationHighlightPref("1")).toBe(true);
  });

  it("treats any unexpected value as enabled", () => {
    expect(readCitationHighlightPref("garbage")).toBe(true);
  });
});
