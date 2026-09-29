"use client";

import { useEffect, useRef } from "react";

/** On a narrow screen the results sit below all settings, so a new result scrolls into view by itself. */
export function useZumErgebnis(anzahl: number) {
  const bereich = useRef<HTMLElement>(null);
  const vorher = useRef(anzahl);
  useEffect(() => {
    if (anzahl > vorher.current && window.innerWidth < 1024) {
      bereich.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    vorher.current = anzahl;
  }, [anzahl]);
  return bereich;
}
