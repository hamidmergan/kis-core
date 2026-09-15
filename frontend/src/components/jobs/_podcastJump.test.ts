import { describe, expect, it } from "vitest";
import { podcastJumpHref, podcastJumpKind } from "./_podcastJump";

const job = (over: Partial<Parameters<typeof podcastJumpKind>[0]> = {}) =>
  ({ tool: "podcast", status: "success", has_download: true, ...over });

describe("Der Rücksprung aus der Auftragsliste", () => {
  it("führt beim wartenden Skript auf Fortsetzen", () => {
    expect(podcastJumpKind(job({ status: "awaiting_user" }))).toBe("resume");
  });

  it("führt nach einem Fehler auf Fortsetzen, dort steht der Knopf dafür", () => {
    expect(podcastJumpKind(job({ status: "failed" }))).toBe("resume");
  });

  it("öffnet einen laufenden Auftrag", () => {
    expect(podcastJumpKind(job({ status: "running" }))).toBe("open");
    expect(podcastJumpKind(job({ status: "pending" }))).toBe("open");
  });

  it("öffnet den fertigen Podcast nur, solange die Datei da ist", () => {
    expect(podcastJumpKind(job())).toBe("open");
    expect(podcastJumpKind(job({ has_download: false }))).toBeNull();
  });

  it("führt einen angehaltenen Podcast zurück zum Weitermachen", () => {
    expect(podcastJumpKind(job({ status: "paused" }))).toBe("resume");
  });

  it("lässt fremde Werkzeuge in Ruhe", () => {
    expect(podcastJumpKind(job({ tool: "screencast_translate" }))).toBeNull();
    expect(podcastJumpKind(job({ tool: "tts" }))).toBeNull();
  });

  it("zeigt auf das Werkzeug mit dem Auftrag im Link", () => {
    expect(podcastJumpHref("abc123")).toBe("/tools/podcast?job=abc123");
  });
});
