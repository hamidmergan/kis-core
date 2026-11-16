import { useEffect, useState } from "react";

/** Asks the backend whether the key of a public link is still good and for whom. */
export function useTokenCheck(endpoint: string, token: string) {
  const [uid, setUid] = useState<string | null>(null);
  const [pruefend, setPruefend] = useState(true);
  const [ungueltig, setUngueltig] = useState(false);
  const [ladefehler, setLadefehler] = useState(false);

  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const r = await fetch(`${endpoint}/${encodeURIComponent(token)}`, { cache: "no-store" });
        if (r.ok) {
          setUid((await r.json()).uid);
        } else if (r.status === 404 || r.status === 410) {
          // Only these two really mean 'no longer exists'.
          setUngueltig(true);
        } else {
          setLadefehler(true);
        }
      } catch {
        setLadefehler(true);
      } finally {
        setPruefend(false);
      }
    })();
  }, [endpoint, token]);

  return { uid, pruefend, ungueltig, setUngueltig, ladefehler };
}
