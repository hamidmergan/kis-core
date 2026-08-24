import { describe, expect, it } from "vitest";

import { screencastJumpKind } from "./_screencastJump";

const JOB = { tool: "screencast_translate", status: "awaiting_user", has_download: false, render_queued_at: null };

describe("screencastJumpKind", () => {
  it("laesst den Nutzer eine wartende Eingabe fortsetzen", () => {
    expect(screencastJumpKind(JOB)).toBe("resume");
  });

  it("schweigt, solange die Skripte noch entstehen", () => {
    expect(screencastJumpKind({ ...JOB, is_generating_scripts: true })).toBe(null);
  });

  it("oeffnet die Warteseite waehrend der Vertonung", () => {
    expect(screencastJumpKind({ ...JOB, status: "running", render_queued_at: "2026-08-23T20:00:00Z" })).toBe("open");
    expect(screencastJumpKind({ ...JOB, status: "queued", render_queued_at: "2026-08-23T20:00:00Z" })).toBe("open");
  });

  it("schweigt, solange nur die Uebersetzung laeuft", () => {
    expect(screencastJumpKind({ ...JOB, status: "running" })).toBe(null);
  });

  it("oeffnet den fertigen Screencast", () => {
    expect(screencastJumpKind({ ...JOB, status: "success", has_download: true })).toBe("open");
  });

  it("schweigt, wenn die Dateien abgelaufen sind", () => {
    expect(screencastJumpKind({ ...JOB, status: "success" })).toBe(null);
  });

  it("geht andere Werkzeuge nichts an", () => {
    expect(screencastJumpKind({ ...JOB, tool: "tts" })).toBe(null);
  });
});
