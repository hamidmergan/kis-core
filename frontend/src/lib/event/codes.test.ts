import { describe, expect, it } from "vitest";
import { CODE_ALPHABET, newCode, newUniqueCode, normalizeCode } from "@/lib/event/codes";

describe("codes", () => {
  it("creates four characters from the safe alphabet", () => {
    for (let i = 0; i < 50; i++) {
      const code = newCode();
      expect(code).toHaveLength(4);
      expect([...code].every((c) => CODE_ALPHABET.includes(c))).toBe(true);
    }
  });

  it("ignores case and spaces", () => {
    expect(normalizeCode(" k7 pm ")).toBe("K7PM");
  });

  it("never repeats a code that is already in use", () => {
    const taken = ["AAAA", "BBBB"];
    for (let i = 0; i < 50; i++) expect(taken).not.toContain(newUniqueCode(taken));
  });
});
