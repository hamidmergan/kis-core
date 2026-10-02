import { describe, expect, it } from "vitest";
import { SEED_CONFIG } from "../../_lib/seed";
import { withTileCount } from "./previewTiles";

const block = SEED_CONFIG.eventBlock;

describe("withTileCount", () => {
  it("cuts from the end and keeps the first tiles untouched", () => {
    const next = withTileCount(block, 1);
    expect(next.tiles.map((tile) => tile.id)).toEqual([block.tiles[0].id]);
  });

  it("fills with kinds that are not there yet", () => {
    const next = withTileCount(block, 4);
    expect(next.tiles).toHaveLength(4);
    const kinds = next.tiles.map((tile) => tile.target.kind);
    expect(new Set(kinds).size).toBe(4);
  });

  it("keeps ids unique when a stand-in name is already taken", () => {
    const taken = { ...block, tiles: [{ ...block.tiles[0], id: "stamp", target: { kind: "info" as const } }] };
    const next = withTileCount(taken, 2);
    expect(next.tiles.map((tile) => tile.id)).toEqual(["stamp", "stamp-2"]);
  });

  it("does not touch the rest of the block", () => {
    const next = withTileCount(block, 3);
    expect(next.heading).toEqual(block.heading);
    expect(next.enabled).toBe(block.enabled);
  });
});
