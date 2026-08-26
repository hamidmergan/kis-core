"use client";

import { useCallback, useEffect, useState } from "react";

export interface DemoWorkspace {
  uuid: string;
  title: string;
  description: string | null;
  source_count: number;
  joined: boolean;
  /** Die Einschreibung stammt aus der Demo, nicht aus einem richtigen Link. */
  via_demo: boolean;
  /** Dem Betrachter gehoert der Kurs, dann gibt es nichts zu betreten. */
  owned: boolean;
}

/** Laedt die Demo-Kurse und haelt Beitreten und Verlassen an einer Stelle. */
export function useDemoWorkspaces() {
  const [items, setItems] = useState<DemoWorkspace[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/ai-assistant/demo/workspaces", { credentials: "include" });
      if (res.ok) setItems(await res.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { load(); }, [load]);

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
