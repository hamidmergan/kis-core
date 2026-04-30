"use client";

import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "ki-assistent-hilde-enabled";
const CHANGE_EVENT = "ki-assistent-hilde-pref:change";

function readPref(): boolean {
  if (typeof window === "undefined") return true;
  try {
    return localStorage.getItem(STORAGE_KEY) !== "0";
  } catch {
    return true;
  }
}

export function useHildePref(): { enabled: boolean; toggle: () => void } {
  // SSR-safe default: assume enabled until we can read localStorage on mount.
  const [enabled, setEnabled] = useState(true);

  useEffect(() => {
    setEnabled(readPref());

    const onCustom = (e: Event) => {
      const detail = (e as CustomEvent<boolean>).detail;
      if (typeof detail === "boolean") setEnabled(detail);
    };
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) setEnabled(readPref());
    };

    window.addEventListener(CHANGE_EVENT, onCustom);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(CHANGE_EVENT, onCustom);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  const toggle = useCallback(() => {
    setEnabled((prev) => {
      const next = !prev;
      try { localStorage.setItem(STORAGE_KEY, next ? "1" : "0"); } catch { /* ignore */ }
      try { window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: next })); } catch { /* ignore */ }
      return next;
    });
  }, []);

  return { enabled, toggle };
}
