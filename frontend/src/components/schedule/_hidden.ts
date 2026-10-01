"use client";

import { useCallback, useEffect, useState } from "react";

/** Only the view is hidden, so it lives in the browser and not on the appointment. */
const STORAGE_KEY = "kis.kalender.ausgeblendet";

/** Hidden workspaces, keyed by uuid, private appointments under their own key. */
const GROUPS_KEY = "kis.kalender.ausgeblendete-gruppen";

function lesen<T extends number | string>(key: string, art: "number" | "string"): Set<T> {
  try {
    const roh = window.localStorage.getItem(key);
    if (!roh) return new Set();
    const liste = JSON.parse(roh);
    return Array.isArray(liste) ? new Set(liste.filter((x) => typeof x === art)) : new Set();
  } catch {
    return new Set();
  }
}

/** A set that survives reloads, toggled one value at a time. */
function useStoredSet<T extends number | string>(key: string, art: "number" | "string") {
  const [werte, setWerte] = useState<Set<T>>(() => new Set());

  // Read only after mounting, otherwise the server renders something else than the browser.
  useEffect(() => { setWerte(lesen<T>(key, art)); }, [key, art]);

  const toggle = useCallback((wert: T) => {
    setWerte((vorher) => {
      const naechste = new Set(vorher);
      if (naechste.has(wert)) naechste.delete(wert);
      else naechste.add(wert);
      try {
        window.localStorage.setItem(key, JSON.stringify([...naechste]));
      } catch { /* ignore */ }
      return naechste;
    });
  }, [key]);

  return [werte, toggle] as const;
}

/** Which appointments the grid leaves out, remembered across reloads. */
export function useHiddenIds() {
  const [hidden, toggleHidden] = useStoredSet<number>(STORAGE_KEY, "number");
  return { hidden, toggleHidden };
}

/** Which workspaces the calendar and the list leave out, remembered across reloads. */
export function useHiddenGroups() {
  const [hiddenGroups, toggleGroup] = useStoredSet<string>(GROUPS_KEY, "string");
  return { hiddenGroups, toggleGroup };
}
