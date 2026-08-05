import { describe, expect, it } from "vitest";
import { exampleSlots, MAX_EXAMPLES, usablePairs } from "./_grammarTopics";

describe("exampleSlots", () => {
  it("always offers one empty row to fill", () => {
    expect(exampleSlots([])).toEqual([{ before: "", after: "" }]);
  });

  it("keeps what is there and adds one empty row", () => {
    const one = [{ before: "Er kommt.", after: "Er käme." }];
    expect(exampleSlots(one)).toHaveLength(2);
    expect(exampleSlots(one)[0]).toEqual(one[0]);
  });

  it("stops offering rows at three pairs", () => {
    const three = [
      { before: "a", after: "b" },
      { before: "c", after: "d" },
      { before: "e", after: "f" },
    ];
    expect(exampleSlots(three)).toHaveLength(MAX_EXAMPLES);
  });
});

describe("usablePairs", () => {
  it("drops the empty row the form always shows", () => {
    const rows = [
      { before: "Er kommt.", after: "Er käme." },
      { before: "", after: "" },
    ];
    expect(usablePairs(rows)).toHaveLength(1);
  });

  it("drops a half filled row", () => {
    expect(usablePairs([{ before: "Er kommt.", after: "  " }])).toHaveLength(0);
  });

  it("drops a pair that transforms nothing", () => {
    // Vorher gleich nachher ist kein Muster, sondern ein Satz.
    expect(usablePairs([{ before: "Er kommt.", after: "Er kommt." }])).toHaveLength(0);
  });

  it("trims what the teacher typed", () => {
    const out = usablePairs([{ before: "  Er kommt. ", after: " Er käme.  " }]);
    expect(out[0]).toEqual({ before: "Er kommt.", after: "Er käme." });
  });

  it("never saves more than three pairs", () => {
    const many = Array.from({ length: 5 }, (_, i) => ({
      before: `Satz ${i}`,
      after: `Um ${i}`,
    }));
    expect(usablePairs(many)).toHaveLength(MAX_EXAMPLES);
  });
});
