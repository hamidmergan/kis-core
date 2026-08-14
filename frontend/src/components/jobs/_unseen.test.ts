import { describe, it, expect } from "vitest";
import { hasUnseenDone, toMs } from "./_unseen";

const seen = toMs("2026-08-13T10:00:00");

describe("toMs", () => {
  it("reads timestamps without a zone marker as UTC", () => {
    expect(toMs("2026-08-13T10:00:00")).toBe(toMs("2026-08-13T10:00:00Z"));
  });
});

describe("hasUnseenDone", () => {
  it("stays quiet while a job is only running", () => {
    expect(hasUnseenDone([{ status: "running", completed_at: null }], seen)).toBe(false);
    expect(hasUnseenDone([{ status: "queued", completed_at: null }], seen)).toBe(false);
    expect(hasUnseenDone([{ status: "pending", completed_at: null }], seen)).toBe(false);
    expect(hasUnseenDone([{ status: "awaiting_user", completed_at: null }], seen)).toBe(false);
  });

  it("reports a job that finished after the last look", () => {
    expect(hasUnseenDone([{ status: "success", completed_at: "2026-08-13T10:00:01" }], seen)).toBe(true);
  });

  it("reports a job that failed after the last look", () => {
    expect(hasUnseenDone([{ status: "failed", completed_at: "2026-08-13T10:00:01" }], seen)).toBe(true);
  });

  it("stays quiet for jobs finished before the last look", () => {
    expect(hasUnseenDone([{ status: "success", completed_at: "2026-08-13T09:59:59" }], seen)).toBe(false);
  });

  it("stays quiet for a finished job without a timestamp", () => {
    expect(hasUnseenDone([{ status: "success", completed_at: null }], seen)).toBe(false);
  });

  it("stays quiet for an empty list", () => {
    expect(hasUnseenDone([], seen)).toBe(false);
  });

  it("finds the fresh job among older ones", () => {
    expect(
      hasUnseenDone(
        [
          { status: "success", completed_at: "2026-08-13T09:00:00" },
          { status: "running", completed_at: null },
          { status: "failed", completed_at: "2026-08-13T10:05:00" },
        ],
        seen,
      ),
    ).toBe(true);
  });
});
