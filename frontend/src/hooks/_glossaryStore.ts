import type { Glossary } from "@/types";

// One shared list for every useGlossaries() caller, so a selector that mounts
// later (inside a modal) paints from memory instead of fetching again.

type Listener = (list: Glossary[]) => void;

let cache: Glossary[] | null = null;
let inflight: Promise<Glossary[]> | null = null;
const listeners = new Set<Listener>();

/** The list already in memory, or null while nothing has been fetched yet. */
export function cached(): Glossary[] | null {
  return cache;
}

/** Registers a consumer and returns the function that unregisters it. */
export function subscribe(fn: Listener): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

/** Stores a new list and hands it to every mounted consumer. */
export function publish(list: Glossary[]): void {
  cache = list;
  for (const fn of [...listeners]) fn(list);
}

/** Resolves from memory, joins a running request, or starts the only one. */
export function load(fetcher: () => Promise<Glossary[]>): Promise<Glossary[]> {
  if (cache) return Promise.resolve(cache);
  if (!inflight) {
    inflight = fetcher()
      .then((list) => {
        publish(list);
        return list;
      })
      .finally(() => {
        inflight = null;
      });
  }
  return inflight;
}

/** Drops the list, used when the signed-in person changes. */
export function invalidateGlossaries(): void {
  cache = null;
  inflight = null;
}

export function __resetForTests(): void {
  invalidateGlossaries();
  listeners.clear();
}
