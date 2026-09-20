"use client";

import { useEffect, useState } from "react";

export interface ModuleEntry {
  uuid: string;
  title: string;
}

export interface ModuleSource {
  uuid: string;
  filename: string;
}

interface WorkspaceRow {
  uuid: string;
  title: string;
  is_active?: boolean;
}

interface SourceRow {
  uuid: string;
  filename: string;
  status: string;
}

/** The real modules of this account, an inactive one is left out because it answers 423. */
export function useModules(selectedUuid: string) {
  const [modules, setModules] = useState<ModuleEntry[] | null>(null);
  const [sources, setSources] = useState<ModuleSource[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/ai-assistant/workspaces", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : []))
      .then((rows: WorkspaceRow[]) => {
        if (cancelled) return;
        setModules(rows.filter((m) => m.is_active !== false).map((m) => ({ uuid: m.uuid, title: m.title })));
      })
      .catch(() => {
        if (!cancelled) setModules([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Only finished sources can be material, the others have no text yet.
  useEffect(() => {
    if (!selectedUuid) {
      setSources(null);
      return;
    }
    let cancelled = false;
    setSources(null);
    fetch(`/api/ai-assistant/workspaces/${selectedUuid}`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : { sources: [] }))
      .then((data: { sources?: SourceRow[] }) => {
        if (cancelled) return;
        setSources((data.sources ?? []).filter((s) => s.status === "ready").map((s) => ({ uuid: s.uuid, filename: s.filename })));
      })
      .catch(() => {
        if (!cancelled) setSources([]);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedUuid]);

  return { modules, sources };
}
