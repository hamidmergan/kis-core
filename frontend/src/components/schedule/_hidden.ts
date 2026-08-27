"use client";

import { useCallback, useEffect, useState } from "react";

/** Only the view is hidden, so it lives in the browser and not on the appointment. */
const STORAGE_KEY = "kis.kalender.ausgeblendet";

function lesen(): Set<number> {
  try {
    const roh = window.localStorage.getItem(STORAGE_KEY);
    if (!roh) return new Set();
    const liste = JSON.parse(roh);
    return Array.isArray(liste) ? new Set(liste.filter((x) => typeof x === "number")) : new Set();
  } catch {
    return new Set();
  }
}

/** Which appointments the grid leaves out, remembered across reloads. */
export function useHiddenIds() {
  const [hidden, setHidden] = useState<Set<number>>(() => new Set());

  // Read only after mounting, otherwise the server renders something else than the browser.
  useEffect(() => { setHidden(lesen()); }, []);

  const toggleHidden = useCallback((id: number) => {
    setHidden((vorher) => {
      const naechste = new Set(vorher);
      if (naechste.has(id)) naechste.delete(id);
      else naechste.add(id);
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify([...naechste]));
      } catch { /* ignore */ }
      return naechste;
    });
  }, []);

  return { hidden, toggleHidden };
}
