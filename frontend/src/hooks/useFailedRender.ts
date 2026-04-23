"use client";

import { useCallback, useState } from "react";

export function useFailedRender() {
  const [jobUuid, setJobUuid] = useState<string | null>(null);
  const [isAuto, setIsAuto] = useState(false);

  const mark = useCallback((uuid: string | null, fromAutoMode: boolean) => {
    setJobUuid(uuid);
    setIsAuto(fromAutoMode);
  }, []);

  const clear = useCallback(() => {
    setJobUuid(null);
    setIsAuto(false);
  }, []);

  return { jobUuid, isAuto, mark, clear, setJobUuid, setIsAuto };
}
