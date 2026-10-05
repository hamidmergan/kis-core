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

/** The stamp card is offered while the event block is live and there are stands to visit. */
export function stampCardOpen(data: PublicEvent | null): boolean {
  return data !== null && data.eventBlock !== null && data.stations.length > 0;
}
