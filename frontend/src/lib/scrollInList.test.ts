import { describe, it, expect } from "vitest";
import { centeredScrollTop } from "./scrollInList";

const list = { top: 100, height: 200, scrollTop: 0, clientHeight: 200, scrollHeight: 1000 };

describe("centeredScrollTop", () => {
  it("puts an item in the middle of the list", () => {
    // Item sits 500 px into the content, 40 px tall, so its centre lands at 100 px in view.
    expect(centeredScrollTop(list, { top: 600, height: 40 })).toBe(420);
  });

  it("counts the current scroll position in", () => {
    expect(centeredScrollTop({ ...list, scrollTop: 300 }, { top: 300, height: 40 })).toBe(420);
  });

  it("never scrolls past the end of the list", () => {
    // The last item cannot be centred, the list stops at its bottom instead of pulling a parent along.
    expect(centeredScrollTop(list, { top: 1060, height: 40 })).toBe(800);
  });

  it("never scrolls above the start", () => {
    expect(centeredScrollTop(list, { top: 110, height: 40 })).toBe(0);
  });
});
