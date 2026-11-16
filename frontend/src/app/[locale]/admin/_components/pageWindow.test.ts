import { describe, it, expect } from "vitest";
import { pageWindow } from "./pageWindow";

describe("pageWindow", () => {
  it("shows every page when there are at most seven", () => {
    expect(pageWindow(1, 3)).toEqual([1, 2, 3]);
    expect(pageWindow(7, 7)).toEqual([1, 2, 3, 4, 5, 6, 7]);
  });

  it("starts at one near the beginning", () => {
    expect(pageWindow(2, 20)).toEqual([1, 2, 3, 4, 5, 6, 7]);
  });

  it("centres on the current page in the middle", () => {
    expect(pageWindow(10, 20)).toEqual([7, 8, 9, 10, 11, 12, 13]);
  });

  it("stays at seven pages near the end", () => {
    expect(pageWindow(20, 20)).toEqual([14, 15, 16, 17, 18, 19, 20]);
    expect(pageWindow(19, 20)).toEqual([14, 15, 16, 17, 18, 19, 20]);
  });

  it("shows the single page", () => {
    expect(pageWindow(1, 1)).toEqual([1]);
  });
});
