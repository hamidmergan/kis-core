"use client";

import { useEffect, useState } from "react";
import { eventApi } from "@/lib/event/api";
import type { PublicEvent } from "@/lib/event/types";

/** The public event data once, null while loading or when the server did not answer. */
export function usePublicEvent(): { data: PublicEvent | null; failed: boolean } {
  const [data, setData] = useState<PublicEvent | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let alive = true;
    eventApi
      .publicEvent()
      .then((d) => alive && setData(d))
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
    };
  }, []);
  return { data, failed };
}

/** Open once the stamp tile is switched on, announced before that, gone once the event is over. */
export function stampCardState(data: PublicEvent | null): "open" | "upcoming" | null {
  if (!data || data.stations.length === 0 || !data.stamp) return null;
  return data.stamp.active ? "open" : "upcoming";
}
