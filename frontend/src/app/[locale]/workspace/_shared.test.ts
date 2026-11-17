import { describe, expect, it } from "vitest";
import { canManage, formatDay } from "./_shared";

describe("formatDay", () => {
  it("writes the day first in German and the month first in English", () => {
    expect(formatDay("2026-12-31T10:00:00Z", "de")).toBe("31.12.2026");
    expect(formatDay("2026-12-31T10:00:00Z", "en")).toBe("12/31/2026");
  });
  it("reads the day in Berlin, where late UTC evening is already tomorrow", () => {
    expect(formatDay("2026-06-30T23:30:00Z", "de")).toBe("01.07.2026");
  });
});

describe("canManage", () => {
  it("lets owners and tutors manage, students not", () => {
    expect(canManage("owner")).toBe(true);
    expect(canManage("tutor")).toBe(true);
    expect(canManage("student")).toBe(false);
  });
});
