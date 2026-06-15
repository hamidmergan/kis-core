"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const STORAGE_KEY = "ki-assistent-hilde-enabled";
const CHANGE_EVENT = "ki-assistent-hilde-pref:change";
const GLOBAL_CHANGED_EVENT = "mascot-global-changed";

function readLocalPref(): boolean {
  if (typeof window === "undefined") return true;
  try {
    return localStorage.getItem(STORAGE_KEY) !== "0";
  } catch {
    return true;
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

export function useHildePref(): { enabled: boolean; toggle: () => void; globalEnabled: boolean } {
  const [localEnabled, setLocalEnabled] = useState(true);
  const [globalEnabled, setGlobalEnabled] = useState(globalCache ?? true);
  const localEnabledRef = useRef(localEnabled);
  localEnabledRef.current = localEnabled;

  useEffect(() => {
    setLocalEnabled(readLocalPref());

    let cancelled = false;
    const load = () => {
      loadGlobal().then((v) => { if (!cancelled) setGlobalEnabled(v); });
    };
    load();

    const onCustom = (e: Event) => {
      const detail = (e as CustomEvent<boolean>).detail;
      if (typeof detail === "boolean") setLocalEnabled(detail);
    };
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) setLocalEnabled(readLocalPref());
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

  // Side effects run in the event handler, not inside the setLocalEnabled
  // updater — an updater runs during render, where dispatching would trigger
  // setState in other listeners mid-render (React's "Cannot update a component
  // while rendering a different component" warning).
  const toggle = useCallback(() => {
    const next = !localEnabledRef.current;
    setLocalEnabled(next);
    try { localStorage.setItem(STORAGE_KEY, next ? "1" : "0"); } catch { /* ignore */ }
    try { window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: next })); } catch { /* ignore */ }
  }, []);

  return { enabled: globalEnabled && localEnabled, toggle, globalEnabled };
}
