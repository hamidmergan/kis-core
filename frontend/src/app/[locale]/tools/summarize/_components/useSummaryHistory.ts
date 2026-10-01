"use client";

import { useCallback, useEffect, useState } from "react";
import { backendApi } from "@/lib/api";

export interface SummaryHistoryEntry {
  job_uuid: string;
  original_filename: string;
  created_at: string;
}

interface Eintrag extends SummaryHistoryEntry {
  tool: string;
  has_download: boolean;
}

const ANZAHL = 10;

/** The last finished summaries of this person, so one of them can be opened again. */
export function useSummaryHistory() {
  const [eintraege, setEintraege] = useState<SummaryHistoryEntry[]>([]);

  const laden = useCallback(async () => {
    try {
      const antwort = await backendApi.fetch(`/jobs/my?tool_filter=summary&limit=${ANZAHL}`);
      if (!antwort.ok) return;
      const { jobs } = (await antwort.json()) as { jobs: Eintrag[] };
      setEintraege(jobs.filter((j) => j.has_download).slice(0, ANZAHL));
    } catch {
      // Without the history the tool still works, the list simply stays as it was.
    }
  }, []);

  useEffect(() => {
    void laden();
    const neu = () => { void laden(); };
    window.addEventListener("kis-jobs-changed", neu);
    return () => window.removeEventListener("kis-jobs-changed", neu);
  }, [laden]);

  return eintraege;
}
