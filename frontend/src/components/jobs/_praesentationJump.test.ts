import { describe, expect, it } from "vitest";
import { praesentationJumpHref, praesentationJumpKind } from "./_praesentationJump";

describe("praesentationJumpKind", () => {
  it("wartet auf die Person bei Gliederung und Folien", () => {
    expect(praesentationJumpKind({ tool: "praesentation", status: "awaiting_user" })).toBe("resume");
    expect(praesentationJumpKind({ tool: "praesentation", status: "paused" })).toBe("resume");
  });
  it("öffnet laufende und fertige Präsentationen", () => {
    expect(praesentationJumpKind({ tool: "praesentation", status: "running" })).toBe("open");
    expect(praesentationJumpKind({ tool: "praesentation", status: "success", has_download: true })).toBe("open");
  });
  it("abgelaufen hat keine Seite", () => {
    expect(praesentationJumpKind({ tool: "praesentation", status: "success", has_download: false })).toBeNull();
    expect(praesentationJumpKind({ tool: "podcast", status: "running" })).toBeNull();
  });
  it("Adresse trägt die Job-Nummer", () => {
    expect(praesentationJumpHref("abc")).toBe("/tools/praesentation?job=abc");
  });
});
