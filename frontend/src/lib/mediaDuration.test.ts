import { describe, it, expect } from "vitest";
import { exceedsTranscriptionLimit, MINUTES_LIMIT_SECONDS } from "./mediaDuration";

describe("exceedsTranscriptionLimit", () => {
  it("accepts a recording under the limit", () => {
    expect(exceedsTranscriptionLimit(60 * 60)).toBe(false);
  });

  it("accepts a recording exactly at the limit", () => {
    // The backend rejects strictly above, so the browser must not reject here
    // and send the user chasing a file the server would have accepted.
    expect(exceedsTranscriptionLimit(MINUTES_LIMIT_SECONDS)).toBe(false);
  });

  it("rejects a recording over the limit", () => {
    expect(exceedsTranscriptionLimit(MINUTES_LIMIT_SECONDS + 1)).toBe(true);
  });

  it("rejects a three-hour lecture", () => {
    expect(exceedsTranscriptionLimit(3 * 60 * 60)).toBe(true);
  });

  it.each([
    ["unknown duration", null],
    ["a stream with no fixed length", Infinity],
    ["an undecodable file", NaN],
  ])("lets the server decide on %s", (_label, value) => {
    expect(exceedsTranscriptionLimit(value as number | null)).toBe(false);
  });

  it("matches the documented 100-minute ceiling", () => {
    expect(MINUTES_LIMIT_SECONDS).toBe(6000);
  });
});
