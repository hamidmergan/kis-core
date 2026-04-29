"use client";

import { useCallback, useState } from "react";

export function useFailedRender() {
  const [jobUuid, setJobUuid] = useState<string | null>(null);

  const mark = useCallback((uuid: string | null) => {
    setJobUuid(uuid);
  }, []);

  const clear = useCallback(() => {
    setJobUuid(null);
  }, []);

  return { jobUuid, mark, clear, setJobUuid };
}
