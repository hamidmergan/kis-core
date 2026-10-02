import { describe, expect, it } from "vitest";
import { EMPTY_CARD, type Card } from "@/lib/event/types";
import { isComplete, openStations, stampedIds, suggestNext } from "@/lib/event/stampLogic";

const stations = [{ id: "a" }, { id: "b" }, { id: "c" }];
const card = (ids: string[]): Card => ({ ...EMPTY_CARD, stamped: Object.fromEntries(ids.map((id, i) => [id, i + 1])) });

describe("stamp logic", () => {
  it("ignores orphaned stamps from removed stations", () => {
    expect(stampedIds(card(["ghost", "a"]), stations)).toEqual(["a"]);
  });

  it("is complete only when every station is stamped", () => {
    expect(isComplete(card(["a", "b"]), stations)).toBe(false);
    expect(isComplete(card(["a", "b", "c"]), stations)).toBe(true);
    expect(isComplete(EMPTY_CARD, [])).toBe(false);
  });

  it("lists the open stations in order", () => {
    expect(openStations(card(["b"]), stations).map((s) => s.id)).toEqual(["a", "c"]);
  });

  it("suggests the next open station after the one just stamped and wraps around", () => {
    expect(suggestNext(card(["a"]), stations, "a")?.id).toBe("b");
    expect(suggestNext(card(["a", "c"]), stations, "c")?.id).toBe("b");
    expect(suggestNext(card(["a", "b", "c"]), stations, "c")).toBeNull();
  });
});
