import { describe, expect, it } from "vitest";
import {
  CODE_ALPHABET,
  LOCK_MS,
  MAX_ATTEMPTS,
  afterWrongCode,
  codeMatches,
  isValidMasterCode,
  lockRemainingMs,
  newMasterCode,
  normalizeCode,
} from "./masterCode";
import { EMPTY_CARD } from "./types";

describe("masterCode", () => {
  it("creates four characters from the safe alphabet", () => {
    for (let i = 0; i < 50; i++) {
      const code = newMasterCode();
      expect(code).toHaveLength(4);
      expect([...code].every((c) => CODE_ALPHABET.includes(c))).toBe(true);
    }
  });

  it("ignores case and spaces", () => {
    expect(normalizeCode(" k7 pm ")).toBe("K7PM");
    expect(codeMatches("k7pm", "K7PM")).toBe(true);
    expect(codeMatches("K7PN", "K7PM")).toBe(false);
  });

  it("rejects look-alike characters and wrong lengths", () => {
    expect(isValidMasterCode("K7PM")).toBe(true);
    expect(isValidMasterCode("K0PM")).toBe(false);
    expect(isValidMasterCode("KIPM")).toBe(false);
    expect(isValidMasterCode("K7P")).toBe(false);
  });

  it("locks after the fifth wrong try", () => {
    let card = EMPTY_CARD;
    for (let i = 0; i < MAX_ATTEMPTS - 1; i++) card = afterWrongCode(card, 1000);
    expect(card.lockUntil).toBeNull();
    card = afterWrongCode(card, 1000);
    expect(card.lockUntil).toBe(1000 + LOCK_MS);
    expect(card.failedAttempts).toBe(0);
    expect(lockRemainingMs(card, 1000 + 10_000)).toBe(LOCK_MS - 10_000);
    expect(lockRemainingMs(card, 1000 + LOCK_MS + 1)).toBe(0);
  });
});
