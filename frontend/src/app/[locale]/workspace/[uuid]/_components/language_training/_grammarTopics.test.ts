import { describe, expect, it } from "vitest";
import {
  editedPairs,
  MAX_EXAMPLES,
  nextTopicId,
  shownSuggestion,
  usablePairs,
} from "./_grammarTopics";

describe("editedPairs", () => {
  it("gives one empty pair when nothing came back", () => {
    expect(editedPairs([])).toEqual([{ before: "", after: "" }]);
  });

  it("hands back every pair, the form shows a row each", () => {
    const pairs = [
      { before: "Er kommt.", after: "Er käme." },
      { before: "Sie geht.", after: "Sie ginge." },
    ];
    expect(editedPairs(pairs)).toEqual(pairs);
  });
});

describe("usablePairs", () => {
  it("drops a half filled pair", () => {
    expect(usablePairs([{ before: "Er kommt.", after: "  " }])).toHaveLength(0);
  });

  it("drops a pair that transforms nothing", () => {
    // Before equals after is not a pattern but a sentence.
    expect(usablePairs([{ before: "Er kommt.", after: "Er kommt." }])).toHaveLength(0);
  });

  it("trims what the teacher typed", () => {
    const out = usablePairs([{ before: "  Er kommt. ", after: " Er käme.  " }]);
    expect(out[0]).toEqual({ before: "Er kommt.", after: "Er käme." });
  });

  it("keeps several distinct musterwege", () => {
    const pairs = [
      { before: "Er beruhigt sich. Er hört Musik.", after: "Er beruhigt sich, indem er Musik hört." },
      { before: "Er beruhigt sich. Er hört Musik.", after: "Er beruhigt sich dadurch, dass er Musik hört." },
    ];
    expect(usablePairs(pairs)).toHaveLength(2);
  });

  it("never saves more than MAX_EXAMPLES pairs", () => {
    const many = Array.from({ length: MAX_EXAMPLES + 2 }, (_, i) => ({
      before: `Satz ${i}`,
      after: `Um ${i}`,
    }));
    expect(usablePairs(many)).toHaveLength(MAX_EXAMPLES);
  });

  it("drops a half filled pair without breaking the ones around it", () => {
    const pairs = [
      { before: "Er kommt.", after: "Er käme." },
      { before: "Sie geht.", after: "  " },
      { before: "Wir sehen.", after: "Wir sähen." },
    ];
    expect(usablePairs(pairs)).toEqual([
      { before: "Er kommt.", after: "Er käme." },
      { before: "Wir sehen.", after: "Wir sähen." },
    ]);
  });
});

describe("nextTopicId", () => {
  const topics = [{ id: 1 }, { id: 2 }, { id: 3 }];

  it("leaves a different choice alone", () => {
    expect(nextTopicId(topics, 3, 1)).toBe(1);
  });

  it("moves up the topic that takes the free place", () => {
    expect(nextTopicId(topics, 2, 2)).toBe(3);
  });

  it("falls back to the one before when the last goes", () => {
    expect(nextTopicId(topics, 3, 3)).toBe(2);
  });

  it("has nothing left to choose when the list runs empty", () => {
    expect(nextTopicId([{ id: 1 }], 1, 1)).toBeNull();
  });

  it("picks the first when nothing was chosen yet", () => {
    expect(nextTopicId(topics, 2, null)).toBe(1);
  });
});

describe("shownSuggestion", () => {
  it("says nothing when there is no suggestion", () => {
    expect(shownSuggestion("Perfekt", "")).toBe("");
    expect(shownSuggestion("Perfekt", "   ")).toBe("");
  });

  it("says nothing when the suggestion repeats what was typed", () => {
    expect(shownSuggestion("Passiv Präsens", "Passiv Präsens")).toBe("");
  });

  it("treats case and spacing as the same name, they are no correction", () => {
    // Otherwise every cleanly typed topic would show a line that says nothing.
    expect(shownSuggestion("passiv  präsens", " Passiv Präsens ")).toBe("");
  });

  it("shows a real correction", () => {
    expect(shownSuggestion("passi", "Passiv Präsens")).toBe("Passiv Präsens");
  });

  it("shows the narrower form for an ambiguous topic", () => {
    // Which form is practised belongs on the tile.
    expect(shownSuggestion("Passiv", "Passiv Präsens")).toBe("Passiv Präsens");
  });
});
