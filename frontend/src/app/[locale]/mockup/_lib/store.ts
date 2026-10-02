"use client";

import { useCallback, useSyncExternalStore } from "react";
import { EMPTY_CARD, type MockupCard, type MockupConfig } from "./types";
import { SEED_CONFIG } from "./seed";

// Raise the config version whenever the seed texts change, so stale saved copies stop shadowing them.
const KEYS = { config: "kis.mockup.config.v3", card: "kis.mockup.card" } as const;
type Slot = keyof typeof KEYS;
type Value<S extends Slot> = S extends "config" ? MockupConfig : MockupCard;
const DEFAULTS = { config: SEED_CONFIG, card: EMPTY_CARD } as { [S in Slot]: Value<S> };
const EVENT = "kis:mockup-change";
const cache: { [S in Slot]?: { raw: string | null; value: Value<S> } } = {};

function read<S extends Slot>(slot: S): Value<S> {
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(KEYS[slot]);
  } catch {
    /* blocked storage */
  }
  const hit = cache[slot];
  if (hit && hit.raw === raw) return hit.value as Value<S>;
  let value = DEFAULTS[slot];
  if (raw) {
    try {
      value = { ...DEFAULTS[slot], ...JSON.parse(raw) };
    } catch {
      /* keep defaults */
    }
  }
  cache[slot] = { raw, value } as (typeof cache)[S];
  return value;
}

function notify() {
  try {
    window.dispatchEvent(new Event(EVENT));
  } catch {
    /* ignore */
  }
}

export function write<S extends Slot>(slot: S, next: Value<S>) {
  try {
    localStorage.setItem(KEYS[slot], JSON.stringify(next));
  } catch {
    /* quota or private mode */
  }
  notify();
}

export function resetMockup(slot?: Slot) {
  for (const key of slot ? [slot] : (Object.keys(KEYS) as Slot[])) {
    try {
      localStorage.removeItem(KEYS[key]);
    } catch {
      /* ignore */
    }
  }
  notify();
}

function subscribe(fn: () => void) {
  window.addEventListener("storage", fn);
  window.addEventListener(EVENT, fn);
  return () => {
    window.removeEventListener("storage", fn);
    window.removeEventListener(EVENT, fn);
  };
}

type Patch<T> = Partial<T> | ((current: T) => T);

/** Same reference until the stored JSON changes, the server render sees the seed. */
export function useMockup<S extends Slot>(slot: S): [Value<S>, (patch: Patch<Value<S>>) => void] {
  const value = useSyncExternalStore(
    subscribe,
    () => read(slot),
    () => DEFAULTS[slot],
  );
  const update = useCallback(
    (patch: Patch<Value<S>>) => {
      const current = read(slot);
      write(slot, typeof patch === "function" ? patch(current) : { ...current, ...patch });
    },
    [slot],
  );
  return [value, update];
}
