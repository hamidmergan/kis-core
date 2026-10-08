"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { backendApi, parseDetail } from "@/lib/api";
import { bilanz, dateiSchluessel, MAX_MATERIAL_CHARS, type Messung } from "@/lib/materialMeasure";

export type Dienst = "podcast" | "praesentation" | "summary" | "screencast" | "pages";

type Auftrag = { key: string; file?: File; sourceId?: string };

const dateiKey = (f: File) => `f:${dateiSchluessel(f)}`;
const quellenKey = (workspace: string, id: string) => `q:${workspace}|${id}`;

/** Counts every picked file or workspace source once, the way the start will count it. */
export function useMaterialMeasure(dienst: Dienst, mode: string, files: File[],
                                   workspaceUuid: string, sourceIds: string[]) {
  const tCommon = useTranslations("common");
  const [messungen, setMessungen] = useState<Record<string, Messung>>({});
  const [max, setMax] = useState(MAX_MATERIAL_CHARS);
  // A measurement starts once per key, a rerender or a second pick of the same file adds nothing.
  const gestartet = useRef(new Set<string>());

  const auftraege = useMemo<Auftrag[]>(() => {
    if (mode === "files") return files.map((f) => ({ key: dateiKey(f), file: f }));
    if (mode === "module" && workspaceUuid) {
      return sourceIds.map((id) => ({ key: quellenKey(workspaceUuid, id), sourceId: id }));
    }
    return [];
  }, [mode, files, workspaceUuid, sourceIds]);

  useEffect(() => {
    const fallback = tCommon("unknownError");
    for (const a of auftraege) {
      if (gestartet.current.has(a.key)) continue;
      gestartet.current.add(a.key);
      setMessungen((alt) => ({ ...alt, [a.key]: { status: "laeuft" } }));
      const body = new FormData();
      if (a.file) body.append("file", a.file);
      else {
        body.append("workspace_uuid", workspaceUuid);
        body.append("source_uuid", a.sourceId ?? "");
      }
      const pfad = a.file ? `/${dienst}/measure` : `/${dienst}/measure/workspace`;
      backendApi.fetch(pfad, { method: "POST", body })
        .then(async (r) => {
          const data = await r.json().catch(() => ({}));
          if (!r.ok) return { status: "fehler", message: parseDetail(data.detail, fallback) } as Messung;
          if (typeof data.maxChars === "number") setMax(data.maxChars);
          return { status: "fertig", chars: Number(data.chars) || 0 } as Messung;
        })
        .catch((): Messung => ({ status: "fehler", message: fallback }))
        .then((m) => setMessungen((alt) => ({ ...alt, [a.key]: m })));
    }
  }, [auftraege, dienst, workspaceUuid, tCommon]);

  return {
    ...bilanz(auftraege.map((a) => messungen[a.key]), max),
    max,
    forFile: (f: File): Messung | undefined => messungen[dateiKey(f)],
    forSource: (id: string): Messung | undefined => messungen[quellenKey(workspaceUuid, id)],
  };
}
