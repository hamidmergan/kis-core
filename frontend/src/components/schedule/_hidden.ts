"use client";

import { useCallback, useEffect, useState } from "react";
import { readPrefs, updatePrefs, type Prefs } from "@/lib/browserStore";

type Feld = "calendarHidden" | "calendarHiddenGroups";

/** Only the view is hidden, so it lives in the browser and not on the appointment. */
function lesen<T extends number | string>(feld: Feld, art: "number" | "string"): Set<T> {
  const liste: unknown = readPrefs()[feld];
  return Array.isArray(liste) ? new Set(liste.filter((x): x is T => typeof x === art)) : new Set();
}

/** A set that survives reloads, toggled one value at a time. */
function useStoredSet<T extends number | string>(feld: Feld, art: "number" | "string") {
  const [werte, setWerte] = useState<Set<T>>(() => new Set());

  // Read only after mounting, otherwise the server renders something else than the browser.
  useEffect(() => { setWerte(lesen<T>(feld, art)); }, [feld, art]);

  const toggle = useCallback((wert: T) => {
    setWerte((vorher) => {
      const naechste = new Set(vorher);
      if (naechste.has(wert)) naechste.delete(wert);
      else naechste.add(wert);
      updatePrefs({ [feld]: naechste.size ? [...naechste] : undefined } as Partial<Prefs>);
      return naechste;
    });
  }, [feld]);

  return [werte, toggle] as const;
}

/** Which appointments the grid leaves out, remembered across reloads. */
export function useHiddenIds() {
  const [hidden, toggleHidden] = useStoredSet<number>("calendarHidden", "number");
  return { hidden, toggleHidden };
}

/** Which workspaces the calendar and the list leave out, remembered across reloads. */
export function useHiddenGroups() {
  const [hiddenGroups, toggleGroup] = useStoredSet<string>("calendarHiddenGroups", "string");
  return { hiddenGroups, toggleGroup };
}
