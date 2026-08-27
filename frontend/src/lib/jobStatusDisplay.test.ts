/** How a job shows its state, previously almost the same in three places. */
import { describe, expect, it } from "vitest";

import { jobStatusDisplay } from "./jobStatusDisplay";

describe("jobStatusDisplay", () => {
  it("zeigt Fortsetzen als Handlung, nicht als Zustand", () => {
    expect(jobStatusDisplay("awaiting_user", {})).toEqual({ kind: "action", key: "awaitingUser" });
  });

  it("gibt laufender Arbeit die Hausfarbe und eine Bewegung", () => {
    expect(jobStatusDisplay("running", {})).toEqual({
      kind: "mark",
      key: "running",
      tone: "brand",
      pulse: true,
    });
  });

  it("erkennt die Skript-Erzeugung als laufende Arbeit", () => {
    expect(jobStatusDisplay("pending", { isGeneratingScripts: true }).key).toBe("running");
  });

  it("stellt abgelaufen vor jeden anderen Zustand", () => {
    expect(jobStatusDisplay("success", { expired: true })).toEqual({
      kind: "mark",
      key: "expired",
      tone: "muted",
    });
  });

  it("faerbt Fertig gruen und Fehler rot", () => {
    expect(jobStatusDisplay("success", {})).toMatchObject({ tone: "success" });
    expect(jobStatusDisplay("failed", {})).toMatchObject({ tone: "error" });
  });

  it("haelt Warteschlange ruhig und Wartend als Hinweis", () => {
    expect(jobStatusDisplay("queued", {})).toEqual({ kind: "mark", key: "queued", tone: "muted" });
    expect(jobStatusDisplay("pending", {})).toEqual({ kind: "mark", key: "pending", tone: "warn" });
  });

  it("behandelt einen unbekannten Zustand wie Wartend", () => {
    expect(jobStatusDisplay("irgendwas", {}).key).toBe("pending");
  });
});
