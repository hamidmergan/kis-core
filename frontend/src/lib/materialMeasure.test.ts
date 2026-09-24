import { describe, expect, it } from "vitest";
import { bilanz, dateiSchluessel } from "./materialMeasure";

describe("bilanz", () => {
  it("adds up what has been counted", () => {
    const b = bilanz([{ status: "fertig", chars: 1000 }, { status: "fertig", chars: 2500 }], 500_000);
    expect(b.total).toBe(3500);
    expect(b.over).toBe(false);
    expect(b.ready).toBe(true);
  });

  it("marks material above the limit as too much", () => {
    const b = bilanz([{ status: "fertig", chars: 300_000 }, { status: "fertig", chars: 200_001 }], 500_000);
    expect(b.over).toBe(true);
    expect(b.ready).toBe(false);
  });

  it("accepts material that fills the limit exactly", () => {
    expect(bilanz([{ status: "fertig", chars: 500_000 }], 500_000).ready).toBe(true);
  });

  it("is not ready while something is still being counted", () => {
    const b = bilanz([{ status: "fertig", chars: 10 }, { status: "laeuft" }], 500_000);
    expect(b.pending).toBe(true);
    expect(b.ready).toBe(false);
  });

  it("treats a pick without a measurement yet as still being counted", () => {
    expect(bilanz([undefined], 500_000).pending).toBe(true);
  });

  it("is not ready when a file could not be read", () => {
    const b = bilanz([{ status: "fehler", message: "kaputt" }], 500_000);
    expect(b.failed).toBe(true);
    expect(b.ready).toBe(false);
  });

  it("is not ready without any material", () => {
    expect(bilanz([], 500_000).ready).toBe(false);
  });
});

describe("dateiSchluessel", () => {
  it("tells two files with the same name but other content apart", () => {
    const a = new File(["a"], "x.pdf", { lastModified: 1 });
    const b = new File(["bb"], "x.pdf", { lastModified: 1 });
    expect(dateiSchluessel(a)).not.toBe(dateiSchluessel(b));
  });
});
