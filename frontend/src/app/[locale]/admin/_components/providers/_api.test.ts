/** Error answers of the provider API reach the admin as a sentence, not as raw JSON. */
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchMeta } from "./_api";

function answer(status: number, body: string) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(body, { status })));
}

afterEach(() => vi.unstubAllGlobals());

describe("error text", () => {
  it("takes the detail of a JSON answer", async () => {
    answer(400, JSON.stringify({ detail: "Name already taken" }));
    await expect(fetchMeta()).rejects.toThrow(/^Name already taken$/);
  });

  it("keeps a plain text body", async () => {
    answer(502, "Bad Gateway");
    await expect(fetchMeta()).rejects.toThrow(/^Bad Gateway$/);
  });

  it("keeps the body when the detail is no sentence", async () => {
    const body = JSON.stringify({ detail: [{ loc: ["body", "name"] }] });
    answer(422, body);
    await expect(fetchMeta()).rejects.toThrow(body);
  });
});
