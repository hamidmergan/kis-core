import { describe, expect, it } from "vitest";
import { renderProgress } from "./_utils";
import type { JobStatus } from "@/lib/api";

const status = (progress: unknown) => ({ progress } as unknown as JobStatus);

describe("renderProgress", () => {
  it("reicht die fertigen Folien durch", () => {
    expect(renderProgress(status({ step: "tts", current: 2, total: 5, fertig: [0, 3] })))
      .toEqual({ kind: "tts", current: 2, total: 5, fertig: [0, 3] });
  });

  it("ein alter Job ohne Liste liefert eine leere Liste", () => {
    expect(renderProgress(status({ step: "tts", current: 2, total: 5 })))
      .toEqual({ kind: "tts", current: 2, total: 5, fertig: [] });
  });

  it("andere Schritte bleiben unveraendert", () => {
    expect(renderProgress(status({ step: "concat" }))).toEqual({ kind: "concat" });
  });
});
