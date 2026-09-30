import { describe, expect, it } from "vitest";
import { FORMATE, GROESSEN, pixelLabel } from "./_utils";

describe("pixelLabel", () => {
  it("zeigt dieselben Pixel wie das Backend", () => {
    // backend/src/features/bild/optionen.py, _PIXEL
    expect(pixelLabel("16:9", "gross")).toBe("1920 × 1088");
    expect(pixelLabel("1:1", "mittel")).toBe("1024 × 1024");
    expect(pixelLabel("9:16", "klein")).toBe("576 × 1024");
  });

  it("hat nur Seiten, die Vielfache von 16 sind", () => {
    for (const f of FORMATE) {
      for (const g of GROESSEN) {
        const [b, h] = pixelLabel(f, g).split(" × ").map(Number);
        expect(b % 16).toBe(0);
        expect(h % 16).toBe(0);
      }
    }
  });
});
