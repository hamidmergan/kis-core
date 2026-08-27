import { describe, expect, it } from "vitest";
import {
  editedPair,
  nextTopicId,
  shownSuggestion,
  usablePairs,
} from "./_grammarTopics";

describe("editedPair", () => {
  it("gives an empty pair when nothing came back", () => {
    expect(editedPair([])).toEqual({ before: "", after: "" });
  });

  it("takes the first pair, the only one the generator reads", () => {
    const pairs = [
      { before: "Er kommt.", after: "Er käme." },
      { before: "Sie geht.", after: "Sie ginge." },
    ];
    expect(editedPair(pairs)).toEqual(pairs[0]);
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

  it("never saves more than the one pair the form shows", () => {
    const many = Array.from({ length: 5 }, (_, i) => ({
      before: `Satz ${i}`,
      after: `Um ${i}`,
    }));
    expect(usablePairs(many)).toHaveLength(1);
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
