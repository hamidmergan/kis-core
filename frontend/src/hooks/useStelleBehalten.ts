"use client";

import { useCallback, useEffect, useRef } from "react";

/** Keeps the playback position when a player switches to another source, so samples compare on the same sentence. */
export function useStelleBehalten<T extends HTMLMediaElement>(quelle: string | null) {
  const ref = useRef<T>(null);
  const stand = useRef<{ zeit: number; laeuft: boolean } | null>(null);

  useEffect(() => {
    const medium = ref.current;
    if (!medium || !quelle || !stand.current) return;
    const { zeit, laeuft } = stand.current;
    stand.current = null;
    const weiter = () => {
      medium.currentTime = Math.min(zeit, medium.duration || zeit);
      if (laeuft) medium.play().catch(() => {});
    };
    if (medium.readyState >= 1) weiter();
    else medium.addEventListener("loadedmetadata", weiter, { once: true });
    return () => medium.removeEventListener("loadedmetadata", weiter);
  }, [quelle]);

  // Called right before the source changes.
  const merken = useCallback(() => {
    const medium = ref.current;
    if (medium) stand.current = { zeit: medium.currentTime, laeuft: !medium.paused && !medium.ended };
  }, []);

  return { ref, merken };
}
