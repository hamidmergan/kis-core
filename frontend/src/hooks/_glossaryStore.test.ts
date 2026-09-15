import { describe, it, expect, beforeEach, vi } from "vitest";
import type { Glossary } from "@/types";
import { cached, invalidateGlossaries, load, publish, subscribe, __resetForTests } from "./_glossaryStore";

const list = (name: string): Glossary[] => [{ id: "1", name, entries: {} } as Glossary];

describe("glossary store", () => {
  beforeEach(() => __resetForTests());

  it("keeps the list so a later consumer needs no second request", async () => {
    const fetcher = vi.fn(async () => list("a"));
    await load(fetcher);
    expect(cached()).toEqual(list("a"));

    await load(fetcher);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("shares one request between consumers that mount together", async () => {
    const fetcher = vi.fn(async () => list("a"));
    const [first, second] = await Promise.all([load(fetcher), load(fetcher)]);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(first).toEqual(second);
  });

  it("hands a failed request back and lets the next consumer retry", async () => {
    const failing = vi.fn(async () => {
      throw new Error("offline");
    });
    await expect(load(failing)).rejects.toThrow("offline");
    expect(cached()).toBeNull();

    const fetcher = vi.fn(async () => list("a"));
    await load(fetcher);
    expect(cached()).toEqual(list("a"));
  });

  it("tells every subscriber about a change", async () => {
    const seen: Glossary[][] = [];
    const stop = subscribe((l) => seen.push(l));
    publish(list("b"));
    expect(seen).toEqual([list("b")]);
    expect(cached()).toEqual(list("b"));

    stop();
    publish(list("c"));
    expect(seen).toHaveLength(1);
  });

  it("drops the list on invalidate so the next load refetches", async () => {
    const fetcher = vi.fn(async () => list("a"));
    await load(fetcher);
    invalidateGlossaries();
    expect(cached()).toBeNull();

    await load(fetcher);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
