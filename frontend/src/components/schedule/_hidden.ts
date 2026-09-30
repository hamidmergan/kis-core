"use client";

import { useCallback, useEffect, useState } from "react";
import { readPrefs, updatePrefs } from "@/lib/browserStore";

/** Only the view is hidden, so it lives in the browser and not on the appointment. */
function lesen(): Set<number> {
  const liste = readPrefs().calendarHidden;
  return Array.isArray(liste) ? new Set(liste.filter((x) => typeof x === "number")) : new Set();
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
      updatePrefs({ calendarHidden: naechste.size ? [...naechste] : undefined });
      return naechste;
    });
  }, []);

  return { hidden, toggleHidden };
}
