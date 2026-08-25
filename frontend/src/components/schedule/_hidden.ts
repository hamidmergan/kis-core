"use client";

import { useCallback, useEffect, useState } from "react";

/** Ausgeblendet wird nur die Ansicht, darum steht es im Browser und nicht am Termin. */
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

/** Welche Termine das Raster weglaesst, gemerkt ueber Neuladen hinweg. */
export function useHiddenIds() {
  const [hidden, setHidden] = useState<Set<number>>(() => new Set());

  // Erst nach dem Mounten lesen, sonst rendert der Server etwas anderes als der Browser.
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
