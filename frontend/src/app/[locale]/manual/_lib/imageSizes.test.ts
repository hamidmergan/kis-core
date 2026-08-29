import { describe, expect, it } from "vitest";
import path from "node:path";
import { imageSizes, pngSize } from "./imageSizes";

const PUBLIC_ROOT = path.join(process.cwd(), "public");

describe("pngSize", () => {
  it("liest Breite und Hoehe aus einem echten Bild", () => {
    const size = pngSize(path.join(PUBLIC_ROOT, "manual", "de", "start-page.png"));
    expect(size).not.toBeNull();
    expect(size!.width).toBeGreaterThan(100);
    expect(size!.height).toBeGreaterThan(100);
  });

  it("liefert null fuer eine fehlende Datei", () => {
    expect(pngSize(path.join(PUBLIC_ROOT, "gibtsnicht.png"))).toBeNull();
  });
});

describe("imageSizes", () => {
  it("halbiert die Pixelmasse, weil doppelt aufgeloest aufgenommen wird", () => {
    const raw = pngSize(path.join(PUBLIC_ROOT, "manual", "de", "start-page.png"))!;
    const sizes = imageSizes("![Start](/manual/de/start-page.png)");
    expect(sizes["/manual/de/start-page.png"].width).toBe(Math.round(raw.width / 2));
  });

  it("uebergeht Bilder, die es nicht gibt", () => {
    expect(imageSizes("![Nix](/manual/de/gibtsnicht.png)")).toEqual({});
  });

  it("liefert nichts fuer Text ohne Bild", () => {
    expect(imageSizes("Nur Text.")).toEqual({});
  });
});
