import { describe, it, expect } from "vitest";
import { popupActionsUrl } from "./_popupActionsUrl";

describe("popupActionsUrl", () => {
  it("hängt den Sprachcode an", () => {
    expect(popupActionsUrl("es")).toBe("/api/ai-assistant/popup-actions?target=es");
  });

  it("lässt den Parameter weg, wenn noch keine Einstellung geladen ist", () => {
    expect(popupActionsUrl(null)).toBe("/api/ai-assistant/popup-actions");
    expect(popupActionsUrl(undefined)).toBe("/api/ai-assistant/popup-actions");
    expect(popupActionsUrl("  ")).toBe("/api/ai-assistant/popup-actions");
  });

  it("maskiert Sonderzeichen", () => {
    expect(popupActionsUrl("a b&c")).toBe("/api/ai-assistant/popup-actions?target=a%20b%26c");
  });
});
