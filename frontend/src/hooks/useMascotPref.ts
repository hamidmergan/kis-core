"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { MascotVariant } from "@/components/ui/Mascot";

export type MascotMode = "off" | "hilde" | "francis";

const STORAGE_KEY = "ki-assistent-mascot";
const LEGACY_KEY = "ki-assistent-hilde-enabled";
const CHANGE_EVENT = "ki-assistent-mascot-pref:change";
const GLOBAL_CHANGED_EVENT = "mascot-global-changed";

// Francis is the default character for everyone who has not picked one.
const DEFAULT_MODE: MascotMode = "francis";

function isMode(v: unknown): v is MascotMode {
  return v === "off" || v === "hilde" || v === "francis";
}

function readLocalMode(): MascotMode {
  if (typeof window === "undefined") return DEFAULT_MODE;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (isMode(raw)) return raw;
    // Migrate the legacy on/off toggle: users who switched the mascot off keep
    // it off, everyone else lands on the new default (Francis).
    if (localStorage.getItem(LEGACY_KEY) === "0") return "off";
    return DEFAULT_MODE;
  } catch {
    return DEFAULT_MODE;
  }
}

let globalCache: boolean | null = null;
let globalInflight: Promise<boolean> | null = null;

async function fetchGlobalEnabled(): Promise<boolean> {
  try {
    const res = await fetch("/api/health/labels", { cache: "no-store" });
    if (!res.ok) return true;
    const data = await res.json();
    return data.mascot_enabled !== false;
  } catch {
    return true;
  }
}

function loadGlobal(): Promise<boolean> {
  if (globalCache !== null) return Promise.resolve(globalCache);
  if (!globalInflight) {
    globalInflight = fetchGlobalEnabled().then((v) => {
      globalCache = v;
      globalInflight = null;
      return v;
    });
  }
  return globalInflight;
}

export function notifyMascotGlobalChanged() {
  globalCache = null;
  globalInflight = null;
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(GLOBAL_CHANGED_EVENT));
  }
}

export interface MascotPref {
  /** The user's raw choice, independent of the global kill switch. */
  mode: MascotMode;
  setMode: (mode: MascotMode) => void;
  /** True when a mascot should actually render (global on AND not "off"). */
  enabled: boolean;
  /** Which character to render. Falls back to the default when "off". */
  variant: MascotVariant;
  /** The admin-controlled global kill switch. */
  globalEnabled: boolean;
}

export function useMascotPref(): MascotPref {
  const [mode, setModeState] = useState<MascotMode>(DEFAULT_MODE);
  const [globalEnabled, setGlobalEnabled] = useState(globalCache ?? true);
  const modeRef = useRef(mode);
  modeRef.current = mode;

  useEffect(() => {
    setModeState(readLocalMode());

    let cancelled = false;
    const load = () => {
      loadGlobal().then((v) => { if (!cancelled) setGlobalEnabled(v); });
    };
    load();

    const onCustom = (e: Event) => {
      const detail = (e as CustomEvent<MascotMode>).detail;
      if (isMode(detail)) setModeState(detail);
    };
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) setModeState(readLocalMode());
    };
    const onGlobal = () => { globalCache = null; globalInflight = null; load(); };

    window.addEventListener(CHANGE_EVENT, onCustom);
    window.addEventListener("storage", onStorage);
    window.addEventListener(GLOBAL_CHANGED_EVENT, onGlobal);
    return () => {
      cancelled = true;
      window.removeEventListener(CHANGE_EVENT, onCustom);
      window.removeEventListener("storage", onStorage);
      window.removeEventListener(GLOBAL_CHANGED_EVENT, onGlobal);
    };
  }, []);

  // Side effects run in the event handler, not inside the setState updater — an
  // updater runs during render, where dispatching would trigger setState in
  // other listeners mid-render (React's "Cannot update a component while
  // rendering a different component" warning).
  const setMode = useCallback((next: MascotMode) => {
    setModeState(next);
    try { localStorage.setItem(STORAGE_KEY, next); } catch { /* ignore */ }
    try { window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: next })); } catch { /* ignore */ }
  }, []);

  const variant: MascotVariant = mode === "hilde" ? "hilde" : "francis";

  return {
    mode,
    setMode,
    enabled: globalEnabled && mode !== "off",
    variant,
    globalEnabled,
  };
}
