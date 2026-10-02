"use client";

import { useSyncExternalStore } from "react";
import { eventApi } from "@/lib/event/api";
import type { EventConfig } from "@/lib/event/types";

export type SaveStatus = "idle" | "saving" | "saved" | "failed";
interface State {
  config: EventConfig | null;
  loadFailed: boolean;
  status: SaveStatus;
  error: string | null;
}

const SAVE_DELAY_MS = 600;
let state: State = { config: null, loadFailed: false, status: "idle", error: null };
const listeners = new Set<() => void>();
let loading = false;
let timer: ReturnType<typeof setTimeout> | undefined;

function set(next: Partial<State>) {
  state = { ...state, ...next };
  listeners.forEach((fn) => fn());
}

export function loadEventConfig() {
  if (state.config || loading) return;
  loading = true;
  set({ loadFailed: false });
  eventApi
    .adminGet()
    .then((config) => set({ config }))
    .catch(() => set({ loadFailed: true }))
    .finally(() => {
      loading = false;
    });
}

async function flush() {
  const config = state.config;
  if (!config) return;
  set({ status: "saving", error: null });
  try {
    const saved = await eventApi.adminPut(config);
    // Keep the local copy while newer edits wait, otherwise take what the server stored.
    set(timer ? { status: "saved" } : { config: saved, status: "saved" });
  } catch (e) {
    set({ status: "failed", error: e instanceof Error ? e.message : null });
  }
}

/** Applies the change at once and saves it shortly after the last edit. */
export function updateEventConfig(patch: Partial<EventConfig> | ((c: EventConfig) => EventConfig)) {
  const current = state.config;
  if (!current) return;
  const config = typeof patch === "function" ? patch(current) : { ...current, ...patch };
  set({ config, status: "idle" });
  clearTimeout(timer);
  timer = setTimeout(() => {
    timer = undefined;
    void flush();
  }, SAVE_DELAY_MS);
}

function subscribe(fn: () => void) {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

const snapshot = () => state;
export function useEventAdminState(): State {
  return useSyncExternalStore(subscribe, snapshot, snapshot);
}

/** The loaded config for components under EventAdminGate, which renders them only after the load. */
export function useEventConfig(): [EventConfig, typeof updateEventConfig] {
  const { config } = useEventAdminState();
  if (!config) throw new Error("useEventConfig needs EventAdminGate");
  return [config, updateEventConfig];
}
