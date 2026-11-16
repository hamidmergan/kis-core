import { describe, expect, it } from "vitest";
import { readLines } from "./_stream";

function body(chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(enc.encode(c));
      controller.close();
    },
  });
}

describe("readLines", () => {
  it("joins a line that arrives in two chunks and counts the chunks", async () => {
    const lines: string[] = [];
    let chunks = 0;
    await readLines(body(["data: a\nda", "ta: b\n"]), (l) => lines.push(l), () => chunks++);
    expect(lines).toEqual(["data: a", "data: b"]);
    expect(chunks).toBe(2);
  });

  it("hands over a last line without a line break and skips a blank rest", async () => {
    const lines: string[] = [];
    await readLines(body(["data: a\ndata: b"]), (l) => lines.push(l));
    expect(lines).toEqual(["data: a", "data: b"]);
    const none: string[] = [];
    await readLines(body(["data: a\n  "]), (l) => none.push(l));
    expect(none).toEqual(["data: a"]);
  });
});
