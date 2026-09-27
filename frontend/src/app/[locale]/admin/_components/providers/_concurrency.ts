/** The buckets a provider can cap, in display order. */
export const CONCURRENCY_BUCKETS = ["llm", "stt", "tts", "image", "embedding", "ocr"] as const;

/** Mirrors the upper limit the backend accepts per bucket. */
export const MAX_CONCURRENCY = 1000;

// Vision counts with the LLM and translation has no field of its own.
const CAPABILITY_BUCKET: Record<string, string> = {
  chat: "llm",
  vision: "llm",
  stt: "stt",
  tts: "tts",
  image_gen: "image",
  image_edit: "image",
  embedding: "embedding",
  ocr: "ocr",
};

/** The buckets that get a field for these capabilities, in the given order. */
export function bucketsFor(
  capabilities: Iterable<string>,
  order: readonly string[] = CONCURRENCY_BUCKETS,
): string[] {
  const wanted = new Set<string>();
  for (const cap of capabilities) {
    const bucket = CAPABILITY_BUCKET[cap];
    if (bucket) wanted.add(bucket);
  }
  return order.filter((b) => wanted.has(b));
}

/** Turns the shown number fields into the stored object, empty and invalid fields drop out. */
export function buildConcurrency(
  fields: Record<string, string>,
  buckets: readonly string[],
): Record<string, number> {
  const out: Record<string, number> = {};
  for (const bucket of buckets) {
    const raw = (fields[bucket] ?? "").trim();
    if (!/^\d+$/.test(raw)) continue;
    const value = Number(raw);
    if (value >= 1 && value <= MAX_CONCURRENCY) out[bucket] = value;
  }
  return out;
}

/** Fills the number fields from the stored object. */
export function concurrencyToFields(
  concurrency: Record<string, number> | undefined,
): Record<string, string> {
  return Object.fromEntries(Object.entries(concurrency ?? {}).map(([k, v]) => [k, String(v)]));
}
