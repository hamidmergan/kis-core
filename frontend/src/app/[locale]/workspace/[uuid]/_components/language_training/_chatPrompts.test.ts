import { describe, it, expect } from "vitest";
import { chatPrompts } from "./_chatPrompts";

describe("chatPrompts", () => {
  it("asks in English for the English interface", () => {
    const p = chatPrompts("en");
    expect(p.tip("Osmosis")).toContain('WITHOUT revealing the answer: "Osmosis"');
    expect(p.termDeep("Osmosis")).toMatch(/^Explain the term "Osmosis"/);
    expect(p.topicDeep("Osmosis")).toMatch(/^Explain the following topic in more detail: "Osmosis"/);
  });

  it("asks in German for every other interface language", () => {
    const p = chatPrompts("de");
    expect(p.tip("Osmose")).toContain("OHNE die Antwort zu verraten");
    expect(p.termDeep("Osmose")).toMatch(/^Erkläre mir den Begriff „Osmose"/);
    expect(p.topicDeep("Osmose")).toMatch(/^Erkläre mir folgendes Thema genauer: „Osmose"/);
  });
});
