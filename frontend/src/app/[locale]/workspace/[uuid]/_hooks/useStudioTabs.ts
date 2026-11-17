"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { PanelKey } from "../_types";

export type StudioTab = "tools" | "glossary" | "notes" | "statistik" | "schedule";

/** A one-off wish for a studio tab, it has to be cleared or it pulls back on every mount. */
export function useStudioTabs(showPanel: (key: PanelKey) => void) {
  const [studioTabRequest, setStudioTabRequest] = useState<{ tab: StudioTab; nonce: number } | null>(null);
  const clearStudioTabRequest = useCallback(() => setStudioTabRequest(null), []);

  const openStudioTab = useCallback((tab: StudioTab) => {
    setStudioTabRequest({ tab, nonce: Date.now() });
    showPanel("studio");
  }, [showPanel]);

  return { studioTabRequest, clearStudioTabRequest, openStudioTab };
}

/** Jumps from the calendar straight to the schedule, once. */
export function useScheduleDeepLink(
  { ready, initialTab, openStudioTab }: { ready: boolean; initialTab: string | null; openStudioTab: (tab: StudioTab) => void },
) {
  const handledRef = useRef(false);
  useEffect(() => {
    if (handledRef.current) return;
    if (!ready || initialTab !== "schedule") return;
    handledRef.current = true;
    openStudioTab("schedule");
    const url = new URL(window.location.href);
    url.searchParams.delete("tab");
    window.history.replaceState({}, "", url.toString());
  }, [ready, initialTab, openStudioTab]);
}
