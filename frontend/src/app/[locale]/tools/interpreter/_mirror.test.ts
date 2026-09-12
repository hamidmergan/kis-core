import { afterEach, describe, expect, it, vi } from "vitest";
import { createMirror } from "./_mirror";
import type { Turn } from "./_types";

const turn = (id: string, original: string): Turn => ({
  id, side: "left", source: "typed", original, translation: "", status: "done", at: 1, edited: false,
});

function setup() {
  const sent: string[] = [];
  const resolvers: (() => void)[] = [];
  const put = (t: Turn) => {
    sent.push(`${t.id}:${t.original}`);
    return new Promise<void>((resolve) => resolvers.push(resolve));
  };
  return { sent, resolvers, mirror: createMirror(put, 1000) };
}

afterEach(() => vi.useRealTimers());

describe("Spiegel zum Server", () => {
  it("schickt den ersten Stand sofort und danach nur den neuesten, einen pro Sekunde", async () => {
    vi.useFakeTimers();
    const { sent, resolvers, mirror } = setup();
    mirror.push(turn("a", "G"));
    mirror.push(turn("a", "Gu"));
    mirror.push(turn("a", "Gut"));
    expect(sent).toEqual(["a:G"]);

    resolvers[0]();
    await vi.advanceTimersByTimeAsync(0);
    expect(sent).toEqual(["a:G"]);
    await vi.advanceTimersByTimeAsync(1000);
    expect(sent).toEqual(["a:G", "a:Gut"]);
  });

  it("hält zwei Sätze auseinander", () => {
    const { sent, mirror } = setup();
    mirror.push(turn("a", "Hallo"));
    mirror.push(turn("b", "Hello"));
    expect(sent).toEqual(["a:Hallo", "b:Hello"]);
  });

  it("flush schickt alles, was noch wartet, und wartet auf die Antwort", async () => {
    vi.useFakeTimers();
    const { sent, resolvers, mirror } = setup();
    mirror.push(turn("a", "G"));
    mirror.push(turn("a", "Gut"));
    let done = false;
    const flushing = mirror.flush().then(() => { done = true; });
    resolvers[0]();
    await vi.advanceTimersByTimeAsync(0);
    expect(sent).toEqual(["a:G", "a:Gut"]);
    expect(done).toBe(false);
    resolvers[1]();
    await flushing;
    expect(done).toBe(true);
  });

  it("cancel lässt fallen, was noch wartet", async () => {
    vi.useFakeTimers();
    const { sent, resolvers, mirror } = setup();
    mirror.push(turn("a", "G"));
    mirror.push(turn("a", "Gut"));
    mirror.cancel();
    resolvers[0]();
    await vi.advanceTimersByTimeAsync(2000);
    expect(sent).toEqual(["a:G"]);
  });
});
