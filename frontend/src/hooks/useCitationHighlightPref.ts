"use client";

import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "ki-assistent-pdf-highlight-enabled";
const CHANGE_EVENT = "ki-assistent-pdf-highlight-pref:change";

// Parse the stored citation-highlight preference. ON by default; only an explicit
// "0" turns it off, so any missing/legacy value keeps highlighting enabled.
// Pure (no DOM) so it can be unit-tested under the node test environment.
export function readCitationHighlightPref(raw: string | null): boolean {
  return raw !== "0";
}

function readPref(): boolean {
  if (typeof window === "undefined") return true;
  try {
    return readCitationHighlightPref(localStorage.getItem(STORAGE_KEY));
  } catch {
    return true;
  }
}

// Per-user, per-browser preference for the yellow citation highlight in the PDF
// viewer. When off, a citation click still jumps to the exact text location but
// draws no marker (see drawCitationHighlight). Purely client-side — there is no
// global/admin flag (unlike useHildePref). Same localStorage + same-tab custom
// event + cross-tab storage event pattern so all open viewers stay in sync.
export function useCitationHighlightPref(): { enabled: boolean; toggle: () => void } {
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
