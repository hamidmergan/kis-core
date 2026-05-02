"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export interface WorkspaceLabels {
  singular: string;
  plural: string;
}

const DEFAULTS: WorkspaceLabels = { singular: "Workspace", plural: "Workspaces" };
const LABELS_CHANGED_EVENT = "workspace-labels-changed";

let cache: WorkspaceLabels | null = null;
let inflight: Promise<WorkspaceLabels> | null = null;

async function fetchLabels(): Promise<WorkspaceLabels> {
  try {
    const res = await api.fetch("/api/health/labels", { cache: "no-store" });
    if (!res.ok) return DEFAULTS;
    const data = await res.json();
    return {
      singular: typeof data.workspace_singular === "string" && data.workspace_singular.trim() ? data.workspace_singular : DEFAULTS.singular,
      plural: typeof data.workspace_plural === "string" && data.workspace_plural.trim() ? data.workspace_plural : DEFAULTS.plural,
    };
  } catch {
    return DEFAULTS;
  }
}

export function useWorkspaceLabel(): WorkspaceLabels {
  const [labels, setLabels] = useState<WorkspaceLabels>(cache ?? DEFAULTS);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      if (cache && !cancelled) setLabels(cache);
      if (!inflight) inflight = fetchLabels().then((l) => { cache = l; inflight = null; return l; });
      inflight.then((l) => { if (!cancelled) setLabels(l); });
    };
    load();
    const onChange = () => { cache = null; load(); };
    window.addEventListener(LABELS_CHANGED_EVENT, onChange);
    return () => {
      cancelled = true;
      window.removeEventListener(LABELS_CHANGED_EVENT, onChange);
    };
  }, []);

  return labels;
}

export function notifyWorkspaceLabelsChanged() {
  cache = null;
  inflight = null;
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(LABELS_CHANGED_EVENT));
  }
}
