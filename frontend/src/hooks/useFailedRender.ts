"use client";

import { useCallback, useState } from "react";

export function useFailedRender() {
  const [jobUuid, setJobUuid] = useState<string | null>(null);
  // Paused means the job stopped after its automatic attempts, it is not a failure.
  const [paused, setPaused] = useState(false);

  const mark = useCallback((uuid: string | null, angehalten = false) => {
    setJobUuid(uuid);
    setPaused(angehalten);
  }, []);

  const clear = useCallback(() => {
    setJobUuid(null);
    setPaused(false);
  }, []);

  return { jobUuid, paused, mark, clear, setJobUuid };
}
