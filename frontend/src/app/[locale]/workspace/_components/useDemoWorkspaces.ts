"use client";

import { useCallback, useEffect, useState } from "react";

export interface DemoWorkspace {
  uuid: string;
  title: string;
  description: string | null;
  source_count: number;
  joined: boolean;
  /** The enrollment comes from the demo, not from a real link. */
  via_demo: boolean;
  /** The viewer owns the course, then there is nothing to enter. */
  owned: boolean;
  /** The one demo course the guided tour runs in. */
  tour: boolean;
}

/** Loads the demo courses and keeps joining and leaving in one place. */
export function useDemoWorkspaces(enabled = true) {
  const [items, setItems] = useState<DemoWorkspace[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/ai-assistant/demo/workspaces", { credentials: "include" });
      if (res.ok) setItems(await res.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { if (enabled) load(); }, [load, enabled]);

  const ruf = useCallback(async (pfad: string, uuid: string | null, marke: string) => {
    setBusy(marke);
    try {
      const res = await fetch(`/api/ai-assistant/demo/${pfad}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(uuid ? { workspace_uuid: uuid } : {}),
      });
      if (res.ok) await load();
      return res.ok;
    } catch {
      return false;
    } finally {
      setBusy(null);
    }
  }, [load]);

  const join = useCallback((uuid: string | null) => ruf("enroll", uuid, uuid ?? "all"), [ruf]);
  const leave = useCallback((uuid: string) => ruf("leave", uuid, uuid), [ruf]);

  return { items, busy, join, leave, reload: load };
}
