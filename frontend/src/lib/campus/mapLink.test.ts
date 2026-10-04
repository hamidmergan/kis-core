import { describe, expect, it } from "vitest";
import { mapLink } from "./mapLink";

describe("mapLink", () => {
  it("carries the language and keeps the path", () => {
    expect(mapLink("https://map.test/campus-map/", "en")).toBe("https://map.test/campus-map/?lang=en");
  });
  it("adds the place and encodes it", () => {
    expect(mapLink("https://map.test/campus-map/", "de", "MFC 8")).toBe("https://map.test/campus-map/?lang=de&show=MFC+8");
  });
  it("replaces a language already in the link", () => {
    expect(mapLink("https://map.test/?lang=de", "en")).toBe("https://map.test/?lang=en");
  });
  it("returns a broken setting unchanged instead of throwing", () => {
    expect(mapLink("campus-map", "de")).toBe("campus-map");
  });
});
