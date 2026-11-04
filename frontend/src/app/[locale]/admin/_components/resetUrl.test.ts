import { describe, expect, it } from "vitest";
import { resetUrl } from "./resetUrl";

describe("resetUrl", () => {
  it("joins origin and token", () => {
    expect(resetUrl("https://kis.example/", "abc")).toBe("https://kis.example/reset-password/abc");
  });
});
