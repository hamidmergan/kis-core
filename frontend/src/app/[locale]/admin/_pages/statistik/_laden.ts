import { useEffect, useState } from "react";

/** Loads one statistics address, the answer to an older address is dropped. */
export function useStatistik<T>(url: string, { behalten = false }: { behalten?: boolean } = {}) {
  const [daten, setDaten] = useState<T | null>(null);
  const [fehler, setFehler] = useState(false);

  useEffect(() => {
    let aktuell = true;
    // Keeping the old numbers avoids a flicker when only the period changes.
    if (!behalten) setDaten(null);
    setFehler(false);
    fetch(url, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d: T) => { if (aktuell) setDaten(d); })
      .catch(() => { if (aktuell) setFehler(true); });
    return () => { aktuell = false; };
  }, [url, behalten]);

  return { daten, fehler };
}
