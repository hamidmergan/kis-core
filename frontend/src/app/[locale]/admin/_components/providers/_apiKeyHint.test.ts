import { describe, expect, it } from "vitest";
import { apiKeyHinweis } from "./_apiKeyHint";

describe("apiKeyHinweis", () => {
  it("beim Bearbeiten mit gespeichertem Schluessel: leer lassen behaelt ihn", () => {
    expect(apiKeyHinweis(true, true)).toBe("dialog.apiKeyEditHint");
  });

  it("beim Bearbeiten ohne gespeicherten Schluessel: es gibt nichts zu behalten", () => {
    expect(apiKeyHinweis(true, false)).toBe("dialog.apiKeyHint");
  });

  it("beim Anlegen: leer lassen, wenn der Endpoint keinen Schluessel braucht", () => {
    expect(apiKeyHinweis(false, false)).toBe("dialog.apiKeyHint");
  });
});
