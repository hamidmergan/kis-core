"use client";

import { useEffect, useState } from "react";
import { useLocale } from "next-intl";
import { api } from "@/lib/api";

export interface WorkspaceLabels {
  singular: string;
  plural: string;
}

interface AllLabels {
  de: WorkspaceLabels;
  en: WorkspaceLabels;
}

const DEFAULTS: AllLabels = {
  de: { singular: "Modul", plural: "Module" },
  en: { singular: "Module", plural: "Modules" },
};
const LABELS_CHANGED_EVENT = "workspace-labels-changed";

let cache: AllLabels | null = null;
let inflight: Promise<AllLabels> | null = null;

function pickString(value: unknown, fallback: string): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

async function fetchLabels(): Promise<AllLabels> {
  try {
    const res = await api.fetch("/api/health/labels", { cache: "no-store" });
    if (!res.ok) return DEFAULTS;
    const data = await res.json();
    return {
      de: {
        singular: pickString(data.workspace_singular_de, DEFAULTS.de.singular),
        plural: pickString(data.workspace_plural_de, DEFAULTS.de.plural),
      },
      en: {
        singular: pickString(data.workspace_singular_en, DEFAULTS.en.singular),
        plural: pickString(data.workspace_plural_en, DEFAULTS.en.plural),
      },
    };
  } catch {
    return DEFAULTS;
  }
}

export function useWorkspaceLabel(): WorkspaceLabels {
  const locale = useLocale();
  const localeKey: keyof AllLabels = locale === "en" ? "en" : "de";
  const [labels, setLabels] = useState<AllLabels>(cache ?? DEFAULTS);

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

  return labels[localeKey];
}

export function notifyWorkspaceLabelsChanged() {
  cache = null;
  inflight = null;
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(LABELS_CHANGED_EVENT));
  }
}
