"use client";

import { useEffect, useState } from "react";
import { checkAuthStatus } from "@/lib/auth";
import { EMPTY_PERMS } from "@/lib/permissions";
import { enabledToolKeys, homeTargets } from "@/lib/modules";
import { useEnabledTools } from "@/hooks/useEnabledTools";
import { stampCardState, usePublicEvent } from "@/lib/event/usePublicEvent";
import type { AuthStatus } from "@/types";

/** True when "/services" really shows the tiles, false when it just redirects to the single target. */
export function useHasStartTiles(): boolean {
  const [auth, setAuth] = useState<AuthStatus | null>(null);
  const { loaded: toolsLoaded, tools: enabledTools } = useEnabledTools();
  const { data: event, failed: eventFailed } = usePublicEvent();

  useEffect(() => {
    checkAuthStatus().then(setAuth);
  }, []);

  if (!auth || !toolsLoaded || (!event && !eventFailed)) return false;
  const perms = auth.permissions ?? EMPTY_PERMS;
  return homeTargets(auth.modules, perms, enabledToolKeys(enabledTools)).length + (stampCardState(event) ? 1 : 0) > 1;
}
